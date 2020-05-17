# Auto-postgres

[![Build Status](https://travis-ci.org/dued/auto-postgres.svg?branch=master)](https://travis-ci.org/dued/auto-postgres)
[![Docker Pulls](https://img.shields.io/docker/pulls/dued/auto-postgres.svg)](https://hub.docker.com/r/dued/auto-postgres)
[![Layers](https://images.microbadger.com/badges/image/dued/auto-postgres.svg)](https://microbadger.com/images/dued/auto-postgres)
[![Commit](https://images.microbadger.com/badges/commit/dued/auto-postgres.svg)](https://microbadger.com/images/dued/auto-postgres)
[![License](https://img.shields.io/github/license/dued/auto-postgres.svg)](https://github.com/dued/auto-postgres/blob/master/LICENSE)

## "Qué es Auto-postgres"

Es una imagen imperativa que configura Postgres antes de iniciarlo.

## ¿Por qué?

Para automatizar el trato con usuarios específicos que acceden desde redes específicas a un servidor postgres.

## ¿Cómo?

Intenta configurar lo mejor posible, diferenciando entre las conexiones realizadas desde LAN (redes docker conectadas) y desde WAN (todas las demás). Esto se hace en el momento del punto de entrada, porque es la única forma de conocer los rangos de IP dinámicos en las redes conectadas.

Luego genera archivos apropiados [`postgres.conf`](https://www.postgresql.org/docs/current/runtime-config.html) y [`pg_hba.conf`](https://www.postgresql.org/docs/current/auth-pg-hba-conf.html)

No valida su configuración, por lo que debe tener en cuenta la configuración adecuada:

- No configura el método de autenticación `cert` si `client.ca.cert.pem` no se proporciona.
- No habilita TLS si `server.cert.pem` y `server.key.pem` no se suministran.
- No publica puertos sin cifrado.
- Usa buenas contraseñas si no usa autorizacion `cert`.

### Variables de entorno

Los valores predeterminados de las variables se encuentran en e [`Dockerfile`][].

El contenedor se configura principalmente a través de estas variables de entorno:

#### `CERTS`

Objeto JSON con algunas o todas estas claves:

- `client.ca.cert.pem`: Contenido de PEM para el parámetro `ssl_ca_file` de Postgres . Permite la autenticación `cert` en clientes remotos de postgres. Es la opción de autenticación remota más segura. Todos los clientes deben autenticarse con un certificado firmado por esta CA.
- `server.cert.pem`: Contenido de PEM para el parámetro `ssl_cert_file` de Postgres . El servidor Postgres se identificará y cifrará la conexión con este certificado.
- `server.key.pem`: Contenido de PEM para el parámetro `ssl_key_file` de Postgres . El servidor de Postgres se identificará y cifrará la conexión con esta clave privada.

Si aprueba `server.cert.pem`, debe aprobar `server.key.pem` también, y viceversa, o el cifrado TLS no se configurará correctamente. También los necesitas a ambos si los usas client.ca.cert.pem.

Es más seguro montar archivos con secretos en lugar de pasar una cadena JSON en una variable env. Puedes montar los equivalentes:

It is safer to mount files with secrets instead of passing a JSON string in an env variable. You can mount the equivalents:

- `/etc/postgres/client.ca.cert.pem`
- `/etc/postgres/server.cert.pem`
- `/etc/postgres/server.key.pem`

#### `CONF_EXTRA`

Cadena con contenido agregado al archivo `postgres.conf` generado.

#### `LAN_AUTH_METHOD`

Método requerido para autenticar clientes que se conectan desde LAN.

#### `LAN_CONNECTION`

Tipo de conexión permitido para conexiones LAN.

#### `LAN_DATABASES`

Matriz JSON con nombres de bases de datos cuyo acceso está permitido desde LAN.

#### `LAN_HBA_TPL`

Plantilla aplicada para cada combinación de LAN CIDR/USER/DATABASE en el archivo `pg_hba.conf`.

Algunos marcadores de posición se pueden expandir. Mira el [`Dockerfile`][] para conocerlos.

#### `LAN_TLS`

Más para habilitar o no TLS en las conexiones LAN.

#### `LAN_USERS`

Usuarios que pueden conectarse desde LAN.


#### `WAN_AUTH_METHOD`

Método requerido para autenticar clientes que se conectan desde WAN.

#### `WAN_CONNECTION`

Tipo de conexión permitido para conexiones WAN. Si es así `hostssl`, solo tendrá efecto cuando se reciban los certificados requeridos.

#### `WAN_DATABASES`

Matriz JSON con nombres de bases de datos cuyo acceso está permitido desde WAN.

#### `WAN_HBA_TPL`

Plantilla aplicada para cada combinación de USER/DATABASE en el archivo `pg_hba.conf`, para conexiones públicas.

Algunos marcadores de posición se pueden expandir. Mira el [`Dockerfile`][] para conocerlos.

#### `WAN_TLS`

Más para habilitar o no TLS en las conexiones WAN.

#### `WAN_USERS`

Usuarios que pueden conectarse desde WAN.

[`Dockerfile`]: https://github.com/dued/auto-postgres/blob/master/Dockerfile
