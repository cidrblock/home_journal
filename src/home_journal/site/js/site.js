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

function search_modal() {
  var search = document.getElementById("search");
  var main_body = document.getElementById("main_body");
  if (search.style.visibility == "visible") {
    search.style.visibility = "hidden";
    search.style.opacity = "0%";
    main_body.style.opacity = "100%";
  } else {
    search.style.visibility = "visible";
    search.style.opacity = "100%";
    main_body.style.opacity = "20%";
    setTimeout(() => {
      search_input.focus();
      search_input.select();
      console.log("Delayed for 1 second.");
    }, 200);
  }
}
