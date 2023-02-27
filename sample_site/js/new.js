
navigator.serviceWorker.addEventListener('message', function (e) {
    const dataTransfer = new DataTransfer();
    var files = e.data.files;
    for (var i = 0; i < files.length; i++) {
        dataTransfer.items.add(files[i]);
    };
    file_input = document.getElementById('images');
    file_input.files = dataTransfer.files;
    file_input.dispatchEvent(new Event('change', { bubbles: true }));
}
);