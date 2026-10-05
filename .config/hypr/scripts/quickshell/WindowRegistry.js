.pragma library

function getScale(mw, mh, userScale) {
    if (arguments.length === 2) {
        userScale = mh;
        mh = mw * (1080.0 / 1920.0);
    }

    if (mw <= 0 || mh <= 0) return 1.0;
    
    let rw = mw / 1920.0;
    let rh = mh / 1080.0;
    let r = Math.min(rw, rh);
    
    let baseScale = 1.0;
    
    if (r <= 1.0) {
        baseScale = Math.max(0.35, Math.pow(r, 0.85));
    } else {
        baseScale = Math.pow(r, 0.5);
    }
    
    return baseScale * (userScale !== undefined ? userScale : 1.0);
}

function s(val, scale) {
    return Math.round(val * scale);
}

function getLayout(name, mx, my, mw, mh, userScale, topbarPosition) {
    let pos = topbarPosition || "top";
    let scale = getScale(mw, mh, userScale);

    let w_bat = s(801, scale), h_bat = s(760, scale);
    let w_net = s(900, scale), h_net = s(700, scale);
    let w_vol = s(450, scale), h_vol = s(700, scale);
    let w_cal = s(1450, scale), h_cal = s(750, scale);
    let w_mus = s(700, scale), h_mus = s(650, scale);
    let w_set = s(450, scale), h_set = mh;
    let w_gui = s(1200, scale), h_gui = s(750, scale);
    let w_app = s(800, scale), h_app = s(700, scale);
    let w_cli = s(800, scale), h_cli = s(700, scale);
    let w_upd = s(950, scale), h_upd = s(850, scale);

    let rx_bat, ry_bat;
    let rx_net, ry_net;
    let rx_vol, ry_vol;
    let rx_cal, ry_cal;
    let rx_mus, ry_mus;
    let rx_set, ry_set;

    if (pos === "bottom") {
        rx_bat = mw - w_bat - s(10, scale); ry_bat = mh - h_bat - s(60, scale);
        rx_net = mw - w_net - s(10, scale); ry_net = mh - h_net - s(60, scale);
        rx_vol = mw - w_vol - s(10, scale); ry_vol = mh - h_vol - s(60, scale);
        rx_cal = Math.floor((mw / 2) - (w_cal / 2)); ry_cal = mh - h_cal - s(60, scale);
        rx_mus = s(10, scale); ry_mus = mh - h_mus - s(60, scale);
        rx_set = 0; ry_set = 0;
    } else if (pos === "left") {
        rx_bat = s(60, scale); ry_bat = Math.max(s(10, scale), mh - h_bat - s(10, scale));
        rx_net = s(60, scale); ry_net = Math.max(s(10, scale), mh - h_net - s(10, scale));
        rx_vol = s(60, scale); ry_vol = Math.max(s(10, scale), mh - h_vol - s(10, scale));
        rx_cal = s(60, scale); ry_cal = Math.floor((mh / 2) - (h_cal / 2));
        rx_mus = s(60, scale); ry_mus = s(10, scale);
        rx_set = 0; ry_set = 0;
    } else if (pos === "right") {
        rx_bat = mw - w_bat - s(60, scale); ry_bat = Math.max(s(10, scale), mh - h_bat - s(10, scale));
        rx_net = mw - w_net - s(60, scale); ry_net = Math.max(s(10, scale), mh - h_net - s(10, scale));
        rx_vol = mw - w_vol - s(60, scale); ry_vol = Math.max(s(10, scale), mh - h_vol - s(10, scale));
        rx_cal = mw - w_cal - s(60, scale); ry_cal = Math.floor((mh / 2) - (h_cal / 2));
        rx_mus = mw - w_mus - s(60, scale); ry_mus = s(10, scale);
        rx_set = mw - w_set; ry_set = 0;
    } else {
        // "top" (default)
        rx_bat = mw - s(805, scale); ry_bat = s(56, scale);
        rx_net = mw - s(904, scale); ry_net = s(56, scale);
        rx_vol = mw - s(455, scale); ry_vol = s(56, scale);
        rx_cal = Math.floor((mw / 2) - (w_cal / 2)); ry_cal = s(56, scale);
        rx_mus = s(5, scale); ry_mus = s(56, scale);
        rx_set = 0; ry_set = 0;
    }

    let base = {
        // --- Top Right Popups ---
        "battery":   { w: w_bat, h: h_bat, rx: rx_bat, ry: ry_bat, comp: "battery/BatteryPopup.qml" },
        "network":   { w: w_net, h: h_net, rx: rx_net, ry: ry_net, comp: "network/NetworkPopup.qml" },
        "volume":    { w: w_vol, h: h_vol, rx: rx_vol, ry: ry_vol, comp: "volume/VolumePopup.qml" },
        
        // --- Central Standard Tools ---
        "applauncher": { w: w_app, h: h_app, rx: Math.floor((mw/2)-(w_app/2)), ry: Math.floor((mh/2)-(h_app/2)), comp: "applauncher/appLauncher.qml" },
        "clipboard": { w: w_cli, h: h_cli, rx: Math.floor((mw/2)-(w_cli/2)), ry: Math.floor((mh/2)-(h_cli/2)), comp: "clipboard/ClipboardManager.qml" },
        "stewart":   { w: s(800, scale), h: s(650, scale), rx: Math.floor((mw/2)-(s(800, scale)/2)), ry: Math.floor((mh/2)-(s(650, scale)/2)), comp: "stewart/stewart.qml" },

        // --- Central Large Tools ---
        "focustime": { w: s(900, scale), h: s(700, scale), rx: Math.floor((mw/2)-(s(900, scale)/2)), ry: Math.floor((mh/2)-(s(700, scale)/2)), comp: "focustime/FocusTimePopup.qml" },

        // --- Extralarge / Custom Centered ---
        "guide":     { w: w_gui, h: h_gui, rx: Math.floor((mw/2)-(w_gui/2)), ry: Math.floor((mh/2)-(h_gui/2)), comp: "guide/GuidePopup.qml" },
        "calendar":  { w: w_cal, h: h_cal, rx: rx_cal, ry: ry_cal, comp: "calendar/CalendarPopup.qml" },
        "updater":   { w: w_upd, h: h_upd, rx: Math.floor((mw/2)-(w_upd/2)), ry: Math.floor((mh/2)-(h_upd/2)), comp: "updater/UpdaterPopup.qml" },
        "wallpaper": { w: mw, h: s(650, scale), rx: 0, ry: (pos === "bottom" ? s(10, scale) : Math.floor((mh/2)-(s(650, scale)/2))), comp: "wallpaper/WallpaperPicker.qml" },
        
        // --- Top Left Edge ---
        "music":     { w: w_mus, h: h_mus, rx: rx_mus, ry: ry_mus, comp: "music/MusicPopup.qml" },

        "movies": {
            w: s(1370, scale),
            h: s(850, scale),
            rx: Math.floor((mw / 2) - (s(1370, scale) / 2)),
            ry: mh - s(850, scale),
            comp: "movies/MovieWidget.qml"
        },
        
        // --- Screen Spanning Panels ---
        "settings":  { w: w_set, h: h_set, rx: rx_set, ry: ry_set, comp: "settings/SettingsPopup.qml" },
        
        // --- Utility ---
        "hidden":    { w: 1, h: 1, rx: -5000 - mx, ry: -5000 - my, comp: "" } 
    };

    if (!base[name]) return null;
    
    let t = base[name];
    t.x = mx + t.rx;
    t.y = my + t.ry;
    
    return t;
}

function getPopupLayout(mw, mh, userScale) {
    if (arguments.length === 2) {
        userScale = mh;
        mh = mw * (1080.0 / 1920.0);
    }
    
    let scale = getScale(mw, mh, userScale);
    return {
        w: s(350, scale),
        marginTop: s(60, scale),
        marginRight: s(20, scale),
        spacing: s(12, scale),
        radius: s(14, scale),
        padding: s(12, scale)
    };
}
