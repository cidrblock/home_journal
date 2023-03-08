document.addEventListener("DOMContentLoaded", function () {
  if (sessionStorage.getItem("mode") == "light") {
    lightMode();
  } else {
    darkMode();
  }
  var element = document.body;
  if (element.style.visibility = "hidden") {
    element.style.visibility = "visible";
  }
});

function lightMode() {
  var element = document.body;
  element.classList.remove("dark");
  element.classList.add("light");
  sessionStorage.setItem("mode", "light");
}

function darkMode() {
  var element = document.body;
  element.classList.remove("light");
  element.classList.add("dark");
  sessionStorage.setItem("mode", "dark");
}

function changeMode() {
  var element = document.body;
  if (element.classList.contains("light")) {
    darkMode();
  } else {
    lightMode();
  }
  console.log("mode changed");
}
