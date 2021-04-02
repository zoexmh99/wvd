function save_options() {
    const use6Channels = document.getElementById("use51").checked;
    const setMaxBitrate = document.getElementById("setMaxBitrate").checked;
    const disableVP9 = document.getElementById("disableVP9").checked;
    const disableAVChigh = document.getElementById("disableAVChigh").checked;

    chrome.storage.sync.set({
        use6Channels,
        setMaxBitrate,
        disableVP9,
        disableAVChigh,
    }, function() {
        var status = document.getElementById('status');
        status.textContent = 'Options saved.';
        setTimeout(function() {
            status.textContent = '';
        }, 750);
    });
}

function restore_options() {
    chrome.storage.sync.get({
        use6Channels: true,
        setMaxBitrate: true,
        disableVP9: false,
        disableAVChigh: false,
    }, function(items) {
        document.getElementById("use51").checked = items.use6Channels;
        document.getElementById("setMaxBitrate").checked = items.setMaxBitrate;
        document.getElementById("disableVP9").checked = items.disableVP9;
        document.getElementById("disableAVChigh").checked = items.disableAVChigh;
    });
}

document.addEventListener('DOMContentLoaded', restore_options);
document.getElementById('save').addEventListener('click', save_options);