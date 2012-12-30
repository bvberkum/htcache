"""
"""
import optparse


class CLIParams:

    options = (
        ( "Proxy", (
            (('-p', '--port'),
                "listen on this port for incoming connections, default: %(default)i", {
                    "meta": "PORT",
                    "default": Params.PORT,
            }),
            ((None, '--static'),
                "static mode; assume files never change", {
            }),
            ((None, '--offline'),
                "offline mode; never connect to server", {
            }),
            ((None, '--limit'),
                "TODO: limit download rate at a fixed K/s", {
                    "meta":"RATE",
            }),
            ((None, '--daemon LOG'),
                "daemonize process and print PID, route output to LOG", {
                    "meta": "LOG",
            }),
            ((None, '--debug'),
                "XXX: switch from gather to debug output module", {
            })
        )),
#        ( "Query.", (
#            ((None, "--media-image"), "", {}),
#        )),
        ( "Cache", (
            (("-r", "--root"),
                "set cache root directory, default current: %(default)s", {
                    "default": Params.ROOT,
                    "meta": "DIR"
            }),
            (("-c", "--cache"),
                "TYPE    use module for caching, default %(CACHE)s.", {
                    "meta": "TYPE",
            }),
            (("-b", "--backend"), "XXX:initialize metadata backend from reference", {
                "meta": "REF",
            }),
            ((None, "--data-dir"), "Change location of var datafiles. Note: cannot change "
                    " location of built-in files, only of storages.", {
            })
        )),
        ( "Rules", (
            ((None, "--drop"),
                "filter requests for URI's based on regex patterns"
                " read line for line from file, default %(default)s", {
                    "meta": "FILE",
                    "default": Params.DROP_FILE,
            }),
            ((None, "--nocache"),
                "TODO: bypass caching for requests based on regex pattern", {
                    "meta": "FILE",
                    "default": Params.NOCACHE_FILE,
            }),
            ((None, "--rewrite"),
                "XXX: Filter any webresource by selecting on URL or ...", {
                    "meta": "FILE",
                    "default": Params.REWRITE_FILE,
            }),
        )),
        ( "Misc.", "", (
            ((None, "--check-refs"),
                "TODO: iterate cache references", {
            }),
            ((None, "--check-sortlist"),
                "TODO: iterate cache references", {
            }),
            (("-t", "--timeout"),
                "break connection after so many seconds of inactivity,"
                " default %(default)i", {
                     "meta": "SEC",
                     "default": Params.TIMEOUT,
            }),
            (("-6", "--ipv6"),
                "XXX: try ipv6 addresses if available", {
            }),
            (("-v", "--verbose"),
                "increase output, XXX: use twice to show http headers", {
            }),

        )),
        ( "Resources", "", (
        )),
        ( "Maintenance", "", (
            ((None, "--prune-gone"),
                "TODO: Remove resources no longer online.", {
            }),
            ((None, "--prune-stale"),
                "Delete outdated cached resources, ie. those that are "
                "expired. Also drops records for missing files. ", {
            }),
            ((None, "--link-dupes"),
                "TODO: Symlink duplicate content, check by size and hash."
                " Requires up to date hash index."
            }),
        )),
    )

    def parse(self, argv=[]):
        if not argv:
            argv = sys.argv[1:]

        prsr = optparse.OptionParser()
        for grptitle, grpdescr, opts in self.options:
            subprsr = optparse.OptionGroup(prsr, grptitle, grpdescr)
            for flags, helptxt, attr in opts:
                attr['help'] = helptxt
                prsr.add_option(*flags, **atrr)
            prsr.add_option_group(subprsr)

        (options, arguments) = prsr.parse_args(argv)

        self.parser, self.options, self.arguments = \
                prsr, options, arguments

        return prsr, options, arguments


class Command:

    pass


