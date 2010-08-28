#!/bin/sh
# /etc/init.d/http-replicator
#
# System-V like init script for http-replicator.
# Note path definitions here and in Params.py:
#
# FIXME: log will get truncated every restart!

# Edit these to suit needs:
LOG=/var/log/http-replicator.log 
LOCK=/var/run/http-replicator.pid
#CACHE=/var/cache/http/
CACHE=/var/cache/www/
FLAGS="-c caches.FileTreeQH"
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
        echo "Starting http-replicator"
        # TODO: check http-replicator status before redirecting output to lock
        http-replicator -v -r $CACHE --log $LOG $FLAGS > $LOCK
    else
        echo "Found "$LOCK", http-replicator already running?"
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
            echo "Stopping http-replicator"
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
    echo "Usage: /etc/init.d/http-replicator {start|stop|restart}"
    exit 1
    ;;
esac

exit 0
