

## .env template
```dotenv

# CC Validation v1.0
VAL_1_0_DB_DRIVER=postgresql+psycopg2
VAL_1_0_DB_USER=<user>
VAL_1_0_DB_PASS=<password>
VAL_1_0_DB_HOST=validation.ad.corekinect.com
VAL_1_0_DB_PORT=5432
VAL_1_0_DB_NAME=test
VAL_1_0_DB_CONNECT_TIMEOUT=5
VAL_1_0_DB_ECHO=false
VAL_1_0_API_AUTH_SERVER_HOST_NAME=https://auth.office.corekinect.cloud:2013
VAL_1_0_API_REST_SERVER_HOST_NAME=https://val.office.corekinect.cloud:2018/api
VAL_1_0_API_AUTH_USERNAME=<user>
VAL_1_0_API_AUTH_PASSWORD=<password>
VAL_1_0_API_KEY=<key>

# CC Office Dev v1.0
DEV_1_0_DB_DRIVER=postgresql+psycopg2
DEV_1_0_DB_USERNAME=<user>
DEV_1_0_DB_PASSWORD=<password>
DEV_1_0_DB_HOST=127.0.0.1
DEV_1_0_DB_PORT=5432
DEV_1_0_DB_DATABASE_NAME=corecloud_office_prod
DEV_1_0_DB_CONNECT_TIMEOUT=5
DEV_1_0_DB_ECHO=false
DEV_1_0_SSH_HOST=dmz-pg02.dmz.corekinect.com
DEV_1_0_SSH_PORT=22
DEV_1_0_SSH_USERNAME=<user>
DEV_1_0_SSH_PASSWORD=<password>
DEV_1_0_SSH_PKEY_PATH=<key_path>
DEV_1_0_SSH_PKEY_PASSPHRASE=<passprhase>
DEV_1_0_SSH_REMOTE_HOST=127.0.0.1
DEV_1_0_SSH_REMOTE_PORT=5432
DEV_1_0_SSH_LOCAL_HOST=127.0.0.1
DEV_1_0_SSH_LOCAL_PORT=0
DEV_1_0_SSH_ALLOW_AGENT=true
DEV_1_0_API_AUTH_SERVER_HOST_NAME=https://auth.office.corekinect.cloud:2013
DEV_1_0_API_REST_SERVER_HOST_NAME=https://dev.office.corekinect.cloud:2022/api
DEV_1_0_API_AUTH_USERNAME=<user>
DEV_1_0_API_AUTH_PASSWORD=<password>
DEV_1_0_API_KEY=<key>

# CC Office Dev v0.9
DEV_0_9_DB_DRIVER=mysql+pymysql
DEV_0_9_DB_USERNAME=<user>
DEV_0_9_DB_PASSWORD=<password>
DEV_0_9_DB_HOST=coreserver005.ad.corekinect.com
DEV_0_9_DB_PORT=3306
DEV_0_9_DB_DATABASE_NAME=CoreCloudTestData
DEV_0_9_DB_CONNECT_TIMEOUT=5
DEV_0_9_DB_ECHO=false

```