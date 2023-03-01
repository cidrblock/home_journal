document.onkeydown = checkKey;

function checkKey(e) {
  e = e || window.event;

  if (e.keyCode == "38") {
    // up arrow
  } else if (e.keyCode == "40") {
    // down arrow
  } else if (e.keyCode == "37") {
    // left arrow
    const elem = document.getElementById("previous");
    window.location.href = elem.href;
  } else if (e.keyCode == "39") {
    // right arrow
    const elem = document.getElementById("next");
    window.location.href = elem.href;
  }
}

window.addEventListener(
  "load",
  function () {
    Lightense("img");
  },
  false
);
