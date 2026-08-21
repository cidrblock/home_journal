document.onkeydown = checkKey;

function checkKey(e) {
  e = e || window.event;
  var modal = document.getElementById("delete-dialog");
  var modal_open = modal && modal.classList.contains("active");
  const tag = (e.target && e.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA") {
    if (e.key === "Escape") {
      close_delete_modal();
    }
    return;
  }

  if (e.key === "Escape") {
    close_delete_modal();
    return;
  }
  if (modal_open) {
    return;
  }

  if (e.keyCode == "37") {
    const elem = document.getElementById("previous");
    window.location.href = elem.href;
  } else if (e.keyCode == "39") {
    const elem = document.getElementById("next");
    window.location.href = elem.href;
  }
}

function delete_modal() {
  var modal = document.getElementById("delete-dialog");
  if (modal.classList.contains("active")) {
    close_delete_modal();
  } else {
    open_delete_modal();
  }
}

function open_delete_modal() {
  document.getElementById("delete-dialog").classList.add("active");
  document.getElementById("delete-overlay").classList.add("active");
  setTimeout(() => {
    var passcode = document.getElementById("delete_passcode");
    passcode.focus();
    passcode.select();
  }, 200);
}

function close_delete_modal() {
  var modal = document.getElementById("delete-dialog");
  var overlay = document.getElementById("delete-overlay");
  if (modal) {
    modal.classList.remove("active");
  }
  if (overlay) {
    overlay.classList.remove("active");
  }
  var error = document.getElementById("delete_error");
  if (error) {
    error.textContent = "";
  }
}

function submit_delete(event) {
  event.preventDefault();
  var error = document.getElementById("delete_error");
  error.textContent = "";
  fetch("/delete", {
    method: "POST",
    body: new FormData(event.target),
  }).then((res) => {
    if (res.ok) {
      window.location.href = "/";
      return;
    }
    if (res.status === 403) {
      error.textContent = "Wrong passcode";
      return;
    }
    error.textContent = "Could not delete this post";
  }).catch(() => {
    error.textContent = "Could not delete this post";
  });
  return false;
}

window.addEventListener(
  "load",
  function () {
    Lightense("img");
  },
  false
);
