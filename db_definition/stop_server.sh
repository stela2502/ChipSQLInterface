#! /bin/bash
exe=$(which pg_ctl)
su - postgres -c "$exe stop -m smart -D $PGDATA"
