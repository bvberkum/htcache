Logging
_______


util.Log.instances
	..
util.Log.instances['htcache']{(),.{facility,level}}
	..


main
	not Runtime.QUIET  # XXX: only apply to console output? not really at place in std log
	and Runtime.ERROR_LEVEL >= Log.level
error
	Log.facility in Runtime.LOG_FACILITIES and 
	Runtime.VERBOSE >= Log.level
components
	Filter events of specific origin component(s).
request-tree
	Emit special structured lines upon updates to the in-memory program tree,
	seen as object trees in three columns: Request, Protocol and Response.
client-tree
	Emit special structured lines upon updates to the in-memory program tree,
	seen with the client IP as root.
resource-tree
	Emit special structured lines upon updates to the Cache and Resource
	instances kept in memory and display object trees in columns.

--log-<facility>-location
--log-<facility>-args = <facility-args-spec>

--log-level main-log-level

Facilities
	main: <level>, <location>
	error: <level>, <location>
	module: <level>, <location>
	components: <level>, <location>, <names>
	client-tree: <location>

E.g. options to enable/configure components facility to log for certain
compnents::

	--log-components-args =<level>,<location>,<names>
	--log-components-level
	--log-components-location
	--log-components-names


signature::

	util.loggers[facility].level(msg, *args)

	util.init_log( facility, *args )


init script
____________
rewriting init script

Tests
______
TODO: review all tests
TODO: need to wrap up sqlstore changes, shoudl fix header errors 

system test 8

finishes download but never completes file

finalize happens when self.cache.tell() == self.descriptor.size (and file is partial)



