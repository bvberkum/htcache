
#PATH=/sbin:/bin:/usr/sbin:/usr/bin
#CONFFILE=/etc/htcache/htcache.conf
LOG=/var/log/htcache.log 
DATADIR=/var/lib/htcache/
ROOT=/var/cache/www/
LOG_LEVEL=7
ERR_LEVEL=5
LOG_FACILITIES=""
#LOG_FACILITIES="$LOG_FACILITIES --log-facility caches "
#LOG_FACILITIES="$LOG_FACILITIES --log-facility cache "
#LOG_FACILITIES="$LOG_FACILITIES --log-facility resource"
#--log-facility protocol"
FLAGS=" -p 8081 --cache caches.FileTree --nodir , "
#--log-level $LOG_LEVEL --error-level $ERR_LEVEL $LOG_FACILITIES"
#FLAGS="--cache caches.FileTree -a %Y/%m/%d/%H:%M- --nodir , "
#--static --offline

# log_daemon_msg() and log_progress_msg() isn't present in present in Sarge.
# Below is a copy of them from lsb-base 3.0-5, for the convenience of back-
# porters.  If the installed version of lsb-base provides these functions,
# they will be used instead.

[ -r /etc/default/htcache ] && source /etc/default/htcache


log_daemon_msg () {
    if [ -z "$1" ]; then
        return 1
    fi

    if [ -z "$2" ]; then
        echo -n "$1:"
        return
    fi
    
    echo -n "$1: $2"
}

log_progress_msg () {
    if [ -z "$1" ]; then
        return 1
    fi
    echo -n " $@"
}

source /lib/lsb/init-functions

if [ ! -x $DAEMON ]; then
	log_failure_msg "htcache appears to be uninstalled."
	exit 5
#elif [ ! -e $CONFFILE ]; then
#	log_failure_msg "htcache appears to be unconfigured."
#	exit 6
fi

# Assert cache dir
if test ! -e $DATADIR
then
    mkdir $DATADIR
fi

htcache_start()
{
    log_daemon_msg "Starting htcached"
    if test ! -e $PIDFILE
    then
        $DAEMON -r $ROOT -d $DATADIR --daemon $LOG $FLAGS --pid-file $PIDFILE
        log_progress_msg "Started htcache"
        log_end_msg $?
    else
        log_failure_msg "Found "$PIDFILE", htcache already running? (PID: $PID)"
        log_end_msg 1
    fi
}

htcache_stop()
{
	log_daemon_msg "Stopping htcache"
    if test ! -e $PIDFILE
    then
        log_progress_msg "Not running"
        log_end_msg 0
    else
        PID=`head -n 1 $PIDFILE`
        if test -n "`ps -p $PID | grep $PID`"
        then
            log_progress_msg "Stopping htcache at $PID"
            kill $PID
            ret=$?
            rm $PIDFILE
            log_end_msg 0
        else
            log_progress_msg "Not running under initial PID, please check and remove "$PIDFILE""
            log_end_msg 1
        fi
    fi
}

## Handle init script argument
case "$1" in
  start)
	#log_daemon_msg "Starting HTTP proxy" "htcache"
	#if [ -s $RSYNC_PIDFILE ] && kill -0 $(cat $RSYNC_PIDFILE) >/dev/null 2>&1; then
	#	log_progress_msg "apparently already running"
	#	log_end_msg 0
	#	exit 0
	#fi
	htcache_start
    ;;
  stop)
  	#log_daemon_msg "Stopping HTTP proxy" "htcache"  
  	#start-stop-daemon --stop --quiet --oknodo --pidfile $PIDFILE
	#log_end_msg $?
	#rm -f $PIDFILE
    htcache_stop
    ;;
  reload|force-reload)  
  	log_failure_msg "Online reload not supported"  
  	#log_warning_msg "Online reload not supported"  
	;;
  restart)
	#log_daemon_msg "Restarting HTTP proxy" "htcache"
    htcache_stop
    htcache_start
    ;;
#  status)
#  	status_of_proc -p PIDFILE "$DAEMON" htcache
#  	exit $? 
#	;;
  *)
    log_failure_msg "Usage: /etc/init.d/htcache" "{start|stop|restart}"
    exit 1
    ;;
esac

exit 0

