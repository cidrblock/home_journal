if (navigator.serviceWorker) {
  navigator.serviceWorker.addEventListener("message", function (e) {
    const dataTransfer = new DataTransfer();
    var files = e.data.files;
    for (var i = 0; i < files.length; i++) {
      dataTransfer.items.add(files[i]);
    }
    file_input = document.getElementById("media");
    file_input.files = dataTransfer.files;
    file_input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function store() {
  var author = document.getElementById("author");
  localStorage.setItem("author", author.value);
}

var wakeLock = null;
var uploadInProgress = false;

async function requestWakeLock() {
  if (!uploadInProgress || !("wakeLock" in navigator)) {
    return;
  }

  try {
    wakeLock = await navigator.wakeLock.request("screen");
    console.log("Screen Wake Lock active");
  } catch (err) {
    console.error(`Wake Lock failed: ${err.name}, ${err.message}`);
  }
}

function releaseWakeLock() {
  if (wakeLock === null) {
    return;
  }

  var lock = wakeLock;
  wakeLock = null;
  lock.release().then(function () {
    console.log("Screen Wake Lock released");
  });
}

document.addEventListener("visibilitychange", function () {
  if (uploadInProgress && document.visibilityState === "visible") {
    requestWakeLock();
  }
});

window.onload = function (e) {
  var author = document.getElementById("author");
  if (window.location.pathname !== "/edit") {
    var saved = localStorage.getItem("author");
    if (saved) {
      author.value = saved;
    }
  }

  document.getElementById("form").addEventListener("submit", function (e) {
    //prevent regular form posting
    e.preventDefault();
    var xhr = new XMLHttpRequest();
    var status = document.getElementById("status");
    var main_body = document.getElementById("main_body");
    var progress_text = document.getElementById("progress_text");
    var files = document.getElementById("media").files;
    var maxUploadSize = Number(this.dataset.maxUploadSize);
    var uploadSize = Array.from(files).reduce(function (total, file) {
      return total + file.size;
    }, 0);

    function showFailure(message) {
      uploadInProgress = false;
      releaseWakeLock();
      status.querySelector("h5").innerText = "Upload failed";
      progress_text.innerText = message;
      main_body.style.opacity = "100%";
    }

    if (maxUploadSize > 0 && uploadSize > maxUploadSize) {
      status.style.visibility = "visible";
      status.style.opacity = "100%";
      showFailure("Selected files exceed the upload limit");
      return;
    }

    uploadInProgress = true;
    requestWakeLock();

    xhr.upload.addEventListener(
      "loadstart",
      function (event) {
        status.style.visibility = "visible";
        status.style.opacity = "100%";
        main_body.style.opacity = "20%";
        status.querySelector("h5").innerText = "Submitting";
        progress_text.innerText = "Starting";
      },
      false
    );

    xhr.upload.addEventListener(
      "progress",
      function (event) {
        var percent = (100 * event.loaded) / event.total;
        ui("#progress", percent);
        progress_text.innerText = Math.round(percent) + "%";
      },
      false
    );

    xhr.upload.addEventListener(
      "load",
      function (event) {
        progress_text.innerText = "Processing";
      },
      false
    );

    xhr.addEventListener(
      "readystatechange",
      function (event) {
        if (event.target.readyState == 4) {
          if (event.target.status >= 200 && event.target.status < 300) {
            uploadInProgress = false;
            releaseWakeLock();
            ui("#progress", 100);
            window.location.replace(event.currentTarget.responseURL);
          } else if (event.target.status == 413) {
            showFailure("Selected files exceed the upload limit");
          } else {
            showFailure("The upload could not be completed");
          }
        }
      },
      false
    );

    xhr.addEventListener(
      "error",
      function () {
        showFailure("The upload could not be completed");
      },
      false
    );

    xhr.addEventListener(
      "abort",
      function () {
        showFailure("The upload was canceled");
      },
      false
    );

    xhr.addEventListener(
      "timeout",
      function () {
        showFailure("The upload timed out");
      },
      false
    );

    xhr.open(this.getAttribute("method"), this.getAttribute("action"), true);
    xhr.send(new FormData(this));
  });
};
