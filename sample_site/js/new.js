if (navigator.serviceWorker) {
  navigator.serviceWorker.addEventListener("message", function (e) {
    const dataTransfer = new DataTransfer();
    var files = e.data.files;
    for (var i = 0; i < files.length; i++) {
      dataTransfer.items.add(files[i]);
    }
    file_input = document.getElementById("images");
    file_input.files = dataTransfer.files;
    file_input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function store() {
  console.log("here");
  var author = document.getElementById("author");
  localStorage.setItem("author", author.value);
  console.log(author);
}

window.onload = function (e) {
  var author = document.getElementById("author");
  author.value = localStorage.getItem("author");
  console.log(author);
};
