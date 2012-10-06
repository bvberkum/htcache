console.debug("Loading htcache.js...");

var htcache_log = function(msg) {
    if (typeof console != 'undefined') {
        console.log(msg);
    }
}

var dhtml_ui = function($){

    var HTCacheMenu = function() {
        this.link = $('script#htcache-dhtml-ui').attr('src').replace('dhtml.js','');
        this.session_id = $('script#htcache-dhtml-ui').attr('class');
    };
    HTCacheMenu.prototype.init_ui = function() {
        $('head')
            .append('<link href="'+this.link+'dhtml.css" rel="stylesheet" type="text/css" media="screen"/>')
        $('body')
            .append('<div id="htcache-floater"><a class="menulink">htcache</a><ul id="htcache-menu" /></div>');

        $('#htcache-menu')
            .append('<li id="htcache-menu-link"></li>');

        $('#htcache-menu')
            .append('<li><pre id="htcache-session"/></li>');

        $('#htcache-info')
            .text([this.link, this.session_id]);

//        this.toggle();
        $('#htcache-floater > a').click(this.toggle);
        $('#htcache-floater > ul').toggleClass('htc-collapsed');
    };
    HTCacheMenu.prototype.toggle = function() {
        $(this).next().toggleClass('htc-collapsed');
    };
    HTCacheMenu.prototype.add_dltree = function(name, tree) {
        var menu = $('#'+name);
        if (menu.length == 0) {
            menu = $('<li><a class="menulink">'+name+'</a><ul id="'+name+'"/></li>');
            $('a', menu).click(this.toggle);
        } else {
            menu = menu.parent();
        };
        var local = this;
        $.each(tree, function(k, v) {
            var subname = name+'_'+k;
            if (typeof v == 'object') {
                var sub = local.add_dltree(subname, v);
                $(menu.children()[1]).append(sub);
            } else {
                $(menu.children()[1]).append('<li><label for="value-'+subname+'">'+k+'</label>: <input id="value-'+subname+'" value="'+escape(v)+'" disabled="disabled"/></li>');
            }
        });
        //$('#'+name).text(tree);
        return menu;
    };
    HTCacheMenu.prototype.add_menu = function(li) {
        $('#htcache-menu').append(li);
    };

    var htcm = new HTCacheMenu();
    htcm.init_ui();

    function load() {
        $.ajax({
                'url': htcm.link + 'control',
                failure: function(e) {
                    console.warn(e);
                },
                success: function(d) {
                    console.warn(d);
                }
            });
        $.ajax({
                'url': htcm.link + 'info',
                failure: function(e) {
                    console.warn(e);
                },
                success: function(d) {
                    var dltree = htcm.add_dltree('htcache-info', d);
                    htcm.add_menu(dltree);
                    $(dltree.children()[1]).toggleClass('htc-collapsed');
                }
            });

        $.ajax({
                'url': htcm.link + 'page-info',
                data: {
                    'url': window.location.href
                },
                failure: function(e) {
                    console.warn(e);
                },
                success: function(d) {
                    props = d[4];
                    feats = d[5];
                    var dltree = htcm.add_dltree('htcache-page-info', props);
                    htcm.add_menu(dltree);
                }
            });
    }
    load();
    var reload = $('<a>reload</a>');
    reload.click(function() {
            $('#htcache-info').parent().remove();
            $('#htcache-page-info').parent().remove();
            load();
    });
    $('#htcache-floater').append(reload);
 }

/* jQuery Initialization */
function insert_jQuery() {
    var script = document.createElement('script');
    script.setAttribute('src', "//ajax.googleapis.com/ajax/libs/jquery/1.8.2/jquery.min.js");
    var head = document.getElementsByTagName('head')[0];
    head.appendChild(script);
    script.onload = function() {
        htcache_log('loaded');
        dhtml_ui(jQuery);
    }
}

window.onload = function() {
    if (typeof jQuery == 'undefined') {
        console.debug("Loading jQuery");
        insert_jQuery();
    } else {
        console.debug("jQuery already present");
        dhtml_ui(jQuery);
    }
}

console.debug("Loaded htcache.js");
