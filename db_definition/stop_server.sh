#! /bin/bash
exe=$(which pg_ctl)
gosu postgres $exe stop -m smart -D $PGDATA
