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

window.onload = function (e) {
  var author = document.getElementById("author");
  author.value = localStorage.getItem("author");

  document.getElementById("form").addEventListener("submit", function (e) {
    //prevent regular form posting
    e.preventDefault();
    var xhr = new XMLHttpRequest();
    var status = document.getElementById("status");
    var main_body = document.getElementById("main_body");
    var progress_text = document.getElementById("progress_text");

    xhr.upload.addEventListener(
      "loadstart",
      function (event) {
        status.style.visibility = "visible";
        status.style.opacity = "100%";
        main_body.style.opacity = "20%";
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
          ui("#progress", 100);
          window.location.replace(event.currentTarget.responseURL);
        }
      },
      false
    );

    xhr.open(this.getAttribute("method"), this.getAttribute("action"), true);
    xhr.send(new FormData(this));
  });
};
