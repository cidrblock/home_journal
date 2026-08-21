document.onkeydown = checkKey;

function checkKey(e) {
  e = e || window.event;
  const tag = (e.target && e.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA") {
    if (e.key === "Escape") {
      close_delete_modal();
    }
    return;
  }

  if (e.key === "Escape") {
    close_delete_modal();
  } else if (e.keyCode == "37") {
    const elem = document.getElementById("previous");
    window.location.href = elem.href;
  } else if (e.keyCode == "39") {
    const elem = document.getElementById("next");
    window.location.href = elem.href;
  }
}

function delete_modal() {
  var modal = document.getElementById("delete");
  var main_body = document.getElementById("main_body");
  if (modal.style.visibility == "visible") {
    close_delete_modal();
  } else {
    modal.style.visibility = "visible";
    modal.style.opacity = "100%";
    main_body.style.opacity = "20%";
    setTimeout(() => {
      var passcode = document.getElementById("delete_passcode");
      passcode.focus();
      passcode.select();
    }, 200);
  }
}

function close_delete_modal() {
  var modal = document.getElementById("delete");
  var main_body = document.getElementById("main_body");
  modal.style.visibility = "hidden";
  modal.style.opacity = "0%";
  main_body.style.opacity = "100%";
  document.getElementById("delete_error").textContent = "";
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
