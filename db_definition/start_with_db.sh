#!/bin/bash
FIRST=0
if [ ! -d $PGDATA ]; then
    mkdir -p $PGDATA
    chown postgres:postgres $PGDATA
    mkdir -p $PGLOG
    chown postgres:postgres $PGLOG

    #
    #echo 'Initializing PostgreSQL...'    

    #FIRST=1
    
    #exe=$(which pg_ctl)
    #other="--auth=password --pwfile /etc/postgres_password.txt"
    #$exe init -D $PGDATA -o '$other'
    
    #sed -i "s|^#unix_socket_directories =.*|unix_socket_directories = '$PGDATA'|" $PGDATA/postgresql.conf

fi
# Start PostgreSQL if not already running
#if ! ls /proc | grep postgress; then
    #echo 'Starting PostgreSQL...'
    #sleep 5
    #exe=$(which pg_ctl)
    #$exe start -D $PGDATA -l $PGLOG/database.log -t 50
#else
    #echo "Server should be up already"
#fi

#if [ "$FIRST" -eq 1 ]; then
    #sleep 5
    #me=$(whoami)
    #PGPASSWORD=$(cat /etc/postgres_password.txt) createdb -h localhost -U $me genome_db
    #PGPASSWORD=$(cat /etc/postgres_password.txt) psql -h localhost -U $me -d genome_db -f /etc/setup_db.sql
#fi