function getElementByXPath(xpath) {
    return document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
}

function maxbitrate_set() {
    window.dispatchEvent(new KeyboardEvent('keydown', {
        keyCode: 83,
        ctrlKey: true,
        altKey: true,
        shiftKey: true,
    }));

    const VIDEO_SELECT = getElementByXPath("//div[text()='Video Bitrate']");
    const AUDIO_SELECT = getElementByXPath("//div[text()='Audio Bitrate']");
    const BUTTON = getElementByXPath("//button[text()='Override']");

    if (!(VIDEO_SELECT && AUDIO_SELECT && BUTTON)){
        return false;
    }

    [VIDEO_SELECT, AUDIO_SELECT].forEach(function (el) {
        let parent = el.parentElement;

        let options = parent.querySelectorAll('select > option');

        for (var i = 0; i < options.length - 1; i++) {
            options[i].removeAttribute('selected');
        }

        options[options.length - 1].setAttribute('selected', 'selected');
    });

    // attempt to click the button immediately
    BUTTON.click();

    return true;
}

function maxbitrate_hide(attempts) {
    // console.log("hide");
    const overrideButton = getElementByXPath("//button[text()='Override']");

    if (overrideButton) {
        overrideButton.click();
    } else if (attempts > 0) {
        setTimeout(() => maxbitrate_hide(attempts - 1), 200);
    }
}

function maxbitrate_run() {
    // console.log("run");
    if (!maxbitrate_set()) {
        setTimeout(maxbitrate_run, 100);
    } else {
        maxbitrate_hide(10);
    }
}

const WATCH_REGEXP = /netflix.com\/watch\/.*/;

let oldLocation;

if(globalOptions.setMaxBitrate) {
    console.log("netflix_max_bitrate.js enabled");
    setInterval(function () {
        let newLocation = window.location.toString();

        if (newLocation !== oldLocation) {
            // console.log("detected navigation");

            oldLocation = newLocation;
            if (WATCH_REGEXP.test(newLocation)) {
                maxbitrate_run();
            }
        }
    }, 500);
}

/*
var data = {};
fetch('http://localhost:29999/widevine_downloader/normal/server/get_netflix_video_profile_mode', {
    method: 'POST', // or 'PUT'
    body: JSON.stringify(data), // data can be `string` or {object}!
    headers:{
        'Content-Type': 'application/json'
    }
    }).then(res => res.json())
    .then(response => {
        console.log('Success:', JSON.stringify(response))
        let mode = JSON.stringify(response);
        let mainScript = document.createElement('script');
        mainScript.type = 'application/javascript';
        if (mode == '0') {
            mainScript.text = `var globalOptions = JSON.parse({use6Channels:"true",setMaxBitrate:"true":disableVP9:"true",disableAVChigh:"true"});`;
        } if (mode == '1') {
            mainScript.text = `var globalOptions = JSON.parse({use6Channels:"true",setMaxBitrate:"true":disableVP9:"true",disableAVChigh:"false"});`;
        } else if (mode == '2') {
            mainScript.text = `var globalOptions = JSON.parse({use6Channels:"true",setMaxBitrate:"true":disableVP9:"false",disableAVChigh:"false"});`;

        }
        document.documentElement.appendChild(mainScript);
    }).catch(error => console.error('Error:', error));
*/
