#!/bin/sh
# /etc/init.d/htcache
#
# System-V like init script for htcache.
# Note path definitions here and in Params.py:
#
# FIXME: this is inadequate and fragile, also htcache may want to handle
# daemonization and running detection internally.

# Edit these to suit needs:
LOG=/var/log/htcache.log 
LOCK=/var/run/htcache.pid
#CACHE=/var/cache/http/
CACHE=/var/cache/www/
FLAGS="--cache caches.FileTreeQ -a %Y/%m/%d/%H:%m- --nodir , "
#--static --offline

# Assert cache dir
if test ! -e $CACHE
then
    mkdir $CACHE
fi

start_replicator()
{
    if test ! -e $LOCK
    then
        echo "Starting htcache"
        # TODO: check htcache status before redirecting output to lock
        htcache -v -r $CACHE --log $LOG $FLAGS > $LOCK
    else
        echo "Found "$LOCK", htcache already running?"
    fi
}

stop_replicator()
{
    if test ! -e $LOCK
    then
        echo "Not running"
    else
        PID=`head -n 1 $LOCK`
        if test -n "`ps -p $PID | grep $PID`"
        then
            echo "Stopping htcache"
            kill $PID
            rm $LOCK
        else
            echo "Not running under initial PID, please check and remove "$LOCK""
        fi
    fi
}

# Handle init script argument
case "$1" in
  start)
    start_replicator
    ;;
  stop)
    stop_replicator
    ;;
  restart)
    stop_replicator
    start_replicator
    ;;
  *)
    echo "Usage: /etc/init.d/htcache {start|stop|restart}"
    exit 1
    ;;
esac

exit 0
