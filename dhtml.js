console.debug("Loading htcache.js...");

var dhtml_ui = function($){

    var link = $('script#htcache-dhtml-ui').attr('src').replace('htcache.js','');
    var session_id = $('script#htcache-dhtml-ui').attr('class');
    console.debug([link, session_id]);

    $.ajax({
            'url': link + 'info',
            failure: function(e) {
                console.warn(e);
            },
            success: function(d) {
                console.info(d);
            }
        });

    $.ajax({
            'url': link + 'page-info',
            failure: function(e) {
                console.warn(e);
            },
            success: function(d) {
                console.info(d);
            }
        });

//    $('head').append('<link href="" rel="stylesheet" type="text/css" media="screen"/>')

 }

/* jQuery Initialization */
function insert_jQuery() {
    var script = document.createElement('script');
    script.setAttribute('src', "//ajax.googleapis.com/ajax/libs/jquery/1.8.2/jquery.min.js");
    var head = document.getElementsByTagName('head')[0];
    head.appendChild(script);
    script.onload = function() {
        console.log('loaded');
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
