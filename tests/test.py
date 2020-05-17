#!/usr/bin/env python3
import json
import os
import time
import unittest

from plumbum import FG, local
from plumbum.cmd import cat, docker  # pylint: disable=import-error
from plumbum.commands.processes import ProcessExecutionError

# Asegúrese de que todas las rutas sean relativas al directorio de pruebas
local.cwd.chdir(os.path.dirname(__file__))
certgen = local["./certgen"]

# Helpers
CONF_EXTRA = """-eCONF_EXTRA=
log_connections = on
log_min_messages = log
"""


class PostgresAutoconfCase(unittest.TestCase):
    """PRUEBA comportamiento de esta imagen docker"""

    @classmethod
    def setUpClass(cls):
        with local.cwd(local.cwd / ".."):
            print("Construyendo la imagen")
            local["./hooks/build"] & FG
        cls.image = "dued/auto-postgres:{}".format(local.env["DOCKER_TAG"])
        cls.cert_files = {"client.ca.cert.pem", "server.cert.pem", "server.key.pem"}
        return super().setUpClass()

    def setUp(self):
        docker("network", "create", "lan")
        docker("network", "create", "wan")
        return super().setUp()

    def tearDown(self):
        try:
            print("Postgres container logs:")
            docker["container", "logs", self.postgres_container] & FG
            docker("container", "stop", self.postgres_container)
            docker("container", "rm", self.postgres_container)
        except AttributeError:
            pass  # No postgres daemon
        docker("network", "rm", "lan", "wan")
        return super().tearDown()

    def _generate_certs(self):
        """Genera certificados para probar la imagen."""
        certgen("ejemplo.localdomain", "test_user")

    def _check_local_connection(self):
        """Verifica que la conexión local funcione bien."""
        # La primera prueba podría fallar mientras bootea postgres
        for attempt in range(10):
            try:
                time.sleep(5)
                # Probar conexiones locales a través del trabajo de socket Unix
                self.assertEqual(
                    "1\n",
                    docker(
                        "container",
                        "exec",
                        self.postgres_container,
                        "psql",
                        "--command",
                        "SELECT 1",
                        "--dbname",
                        "test_db",
                        "--no-align",
                        "--tuples-only",
                        "--username",
                        "test_user",
                    ),
                )
            except AssertionError:
                if attempt < 9:
                    print("Failure number {}. Retrying...".format(attempt))
                else:
                    raise
            else:
                continue

    def _check_password_auth(self, host=None):
        """La conexión con contraseña de autenticación funciona bien."""
        if not host:
            # Conectarse a través de LAN por defecto
            host = self.postgres_container[:12]
        self.assertEqual(
            "1\n",
            docker(
                "container",
                "run",
                "--network",
                "lan",
                "-e",
                "PGDATABASE=test_db",
                "-e",
                "PGPASSWORD=test_password",
                "-e",
                "PGSSLMODE=disable",
                "-e",
                "PGUSER=test_user",
                self.image,
                "psql",
                "--host",
                host,
                "--command",
                "SELECT 1",
                "--no-align",
                "--tuples-only",
            ),
        )

    def _connect_wan_network(self, alias="ejemplo.localdomain"):
        """Enlace una nueva red para imitar conexiones WAN."""
        docker("network", "connect", "--alias", alias, "wan", self.postgres_container)

    def _check_cert_auth(self):
        """La conexión con cert auth funciona bien."""
        # La prueba conexión con cert auth funciona bien
        self.assertEqual(
            "1\n",
            docker(
                "container",
                "run",
                "--network",
                "wan",
                "-e",
                "PGDATABASE=test_db",
                "-e",
                "PGSSLCERT=/certs/client.cert.pem",
                "-e",
                "PGSSLKEY=/certs/client.key.pem",
                "-e",
                "PGSSLMODE=verify-full",
                "-e",
                "PGSSLROOTCERT=/certs/server.ca.cert.pem",
                "-e",
                "PGUSER=test_user",
                CONF_EXTRA,
                "-v",
                "{}:/certs".format(local.cwd),
                self.image,
                "psql",
                "--host",
                "ejemplo.localdomain",
                "--command",
                "SELECT 1",
                "--no-align",
                "--tuples-only",
            ),
        )

    def test_server_certs_var(self):
        """Prueba que el servidor habilita autenticación de cert a través de env vars."""
        with local.tempdir() as tdir:
            with local.cwd(tdir):
                self._generate_certs()
                certs_var = {name: cat(name) for name in self.cert_files}
                self.postgres_container = docker(
                    "container",
                    "run",
                    "-d",
                    "--network",
                    "lan",
                    "-e",
                    "CERTS=" + json.dumps(certs_var),
                    "-e",
                    "POSTGRES_DB=test_db",
                    "-e",
                    "POSTGRES_PASSWORD=test_password",
                    "-e",
                    "POSTGRES_USER=test_user",
                    CONF_EXTRA,
                    self.image,
                ).strip()
                self._check_local_connection()
                self._check_password_auth()
                self._connect_wan_network()
                self._check_cert_auth()

    def test_server_certs_mount(self):
        """El test server habilita la autenticación cert a través de montajes de archivos."""
        with local.tempdir() as tdir:
            with local.cwd(tdir):
                self._generate_certs()
                cert_vols = [
                    "-v{0}/{1}:/etc/postgres/{1}".format(local.cwd, cert)
                    for cert in [
                        "client.ca.cert.pem",
                        "server.cert.pem",
                        "server.key.pem",
                    ]
                ]
                self.postgres_container = docker(
                    "container",
                    "run",
                    "-d",
                    "--network",
                    "lan",
                    "-e",
                    "POSTGRES_DB=test_db",
                    "-e",
                    "POSTGRES_PASSWORD=test_password",
                    "-e",
                    "POSTGRES_USER=test_user",
                    CONF_EXTRA,
                    *cert_vols,
                    self.image,
                ).strip()
                self._check_local_connection()
                self._check_password_auth()
                self._connect_wan_network()
                self._check_cert_auth()

    def test_no_certs_lan(self):
        """La configuración normal sin certs funciona bien."""
        self.postgres_container = docker(
            "container",
            "run",
            "-d",
            "--network",
            "lan",
            "-e",
            "POSTGRES_DB=test_db",
            "-e",
            "POSTGRES_PASSWORD=test_password",
            "-e",
            "POSTGRES_USER=test_user",
            CONF_EXTRA,
            self.image,
        ).strip()
        self._check_local_connection()
        self._check_password_auth()
        self._connect_wan_network()
        with self.assertRaises(ProcessExecutionError):
            self._check_password_auth("ejemplo.localdomain")

    def test_no_certs_wan(self):
        """El acceso a WAN sin cifrar funciona (aunque esto es peligroso)."""
        self.postgres_container = docker(
            "container",
            "run",
            "-d",
            "--network",
            "lan",
            "-e",
            "POSTGRES_DB=test_db",
            "-e",
            "POSTGRES_PASSWORD=test_password",
            "-e",
            "POSTGRES_USER=test_user",
            "-e",
            "WAN_AUTH_METHOD=md5",
            "-e",
            "WAN_CONNECTION=host",
            CONF_EXTRA,
            self.image,
        ).strip()
        self._check_local_connection()
        self._check_password_auth()
        self._connect_wan_network()
        with self.assertRaises(ProcessExecutionError):
            self._check_password_auth("ejemplo.localdomain")

    def test_certs_falsy_lan(self):
        """La configuración con valores falsos para certs funciona bien."""
        self.postgres_container = docker(
            "container",
            "run",
            "-d",
            "--network",
            "lan",
            "-e",
            "POSTGRES_DB=test_db",
            "-e",
            "POSTGRES_PASSWORD=test_password",
            "-e",
            "POSTGRES_USER=test_user",
            CONF_EXTRA,
            "-e",
            "CERTS={}".format(
                json.dumps(
                    {
                        "client.ca.cert.pem": False,
                        "server.cert.pem": False,
                        "server.key.pem": False,
                    }
                )
            ),
            self.image,
        ).strip()
        self._check_local_connection()
        self._check_password_auth()
        self._connect_wan_network()
        with self.assertRaises(ProcessExecutionError):
            self._check_password_auth("ejemplo.localdomain")


if __name__ == "__main__":
    unittest.main()
