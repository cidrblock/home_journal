document.addEventListener("DOMContentLoaded", function () {
  if (localStorage.getItem("mode") == "light") {
    lightMode();
  } else {
    darkMode();
  }
  var element = document.body;
  if ((element.style.visibility = "hidden")) {
    element.style.visibility = "visible";
  }
});

function lightMode() {
  var element = document.body;
  element.classList.remove("dark");
  element.classList.add("light");
  localStorage.setItem("mode", "light");
}

function darkMode() {
  var element = document.body;
  element.classList.remove("light");
  element.classList.add("dark");
  localStorage.setItem("mode", "dark");
}

function changeMode() {
  var element = document.body;
  if (element.classList.contains("light")) {
    darkMode();
  } else {
    lightMode();
  }
}
