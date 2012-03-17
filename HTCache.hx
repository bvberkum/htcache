package;

import js.Dom;

class HTCache {

    /**
     * Event handlers
     */
	static function onKeyUp(evt:js.Event) {
        //var l = js.Lib.window.location;

        /* Open floater: ctrl+alt+shift+p */
        if (evt.keyCode == 80) { 
			if (evt.altKey && evt.ctrlKey && evt.shiftKey) {
                //l.href = l.href + "/permanent-url";
            }
		}
        else if (evt.keyCode == 109) { // ctrl+'-'
            updateLayout();
        }
        else if (evt.keyCode == 61) { // ctrl+'+'
            updateLayout();
        }
	}

    static function onLoad(evt) {
        var htcache_proxy_menu = js.Lib.document.getElementById("htcache_proxy_menu");

        //var br = js.Lib.document.createElement("br");
        //br.style.clear = "left";
        //contents.appendChild(br);

        // XXX: figure out a way to set global cookie? iframe from proxy?
        //var cookie = js.Cookie.get("htcache");

        var proxy_hostinfo = "dm:8080";

        var xhr = new js.XMLHttpRequest();
        xhr.setRequestHeader("Referer", js.Lib.window.location.href);
        xhr.onreadystatechange = function() {
            if (xhr.readyState == 4) {
                var data = js.Lib.eval(xhr.responseText);
                untyped window.console.log(data);
            }
        };
        xhr.open("GET", "http://"+ proxy_hostinfo +"/page-info", true);

        updateLayout();
    }

    static function onResize(evt) {
        updateLayout();
    }

    /** Init/update GUI */
    static function updateLayout() {
    }

    /** Static entry-point */
    static function main() {
		js.Lib.document.onkeyup = onKeyUp;
		js.Lib.document.onresize = onResize;
        js.Lib.window.onload = onLoad;
    }
}
