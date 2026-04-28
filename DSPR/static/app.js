const loginPanel = document.getElementById("login-panel");
const signupPanel = document.getElementById("signup-panel");
const uploadCard = document.getElementById("upload-card");
const postsGrid = document.getElementById("posts");
const emptyState = document.getElementById("empty-state");
const showLoginButton = document.getElementById("show-login");
const showSignupButton = document.getElementById("show-signup");
const switchToSignup = document.getElementById("switch-to-signup");
const switchToLogin = document.getElementById("switch-to-login");
const showSignupCta = document.getElementById("show-signup-cta");
const logoutButton = document.getElementById("logout-button");

const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");
const uploadForm = document.getElementById("upload-form");

function showPanel(panel) {
  const loginActive = panel === "login";
  loginPanel.classList.toggle("hidden", !loginActive);
  signupPanel.classList.toggle("hidden", loginActive);
  showLoginButton.classList.toggle("active", loginActive);
  showSignupButton.classList.toggle("active", !loginActive);
}

showLoginButton.addEventListener("click", () => showPanel("login"));
showSignupButton.addEventListener("click", () => showPanel("signup"));
switchToSignup.addEventListener("click", () => showPanel("signup"));
switchToLogin.addEventListener("click", () => showPanel("login"));
showSignupCta.addEventListener("click", () => showPanel("signup"));

async function fetchJson(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function formatDate(isoText) {
  return new Date(isoText).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function renderPosts(posts) {
  postsGrid.innerHTML = "";
  if (!posts.length) {
    emptyState.classList.remove("hidden");
    return;
  }
  emptyState.classList.add("hidden");
  posts.forEach(post => {
    const card = document.createElement("article");
    card.className = "post-card";
    card.innerHTML = `
      <img src="${post.image}" alt="${post.caption || post.username} ride" />
      <div class="post-body">
        <h4>${post.name}</h4>
        <p>${post.caption || "No caption yet."}</p>
        <div class="post-meta">${post.username} · ${formatDate(post.created)}</div>
      </div>
    `;
    postsGrid.appendChild(card);
  });
}

async function refreshFeed() {
  try {
    const data = await fetchJson("/api/posts");
    renderPosts(data.posts);
  } catch (error) {
    console.error(error);
  }
}

async function checkSession() {
  try {
    const data = await fetchJson("/api/me");
    if (data.user) {
      uploadCard.classList.remove("hidden");
      loginPanel.classList.add("hidden");
      signupPanel.classList.add("hidden");
    } else {
      uploadCard.classList.add("hidden");
      showPanel("login");
    }
  } catch (error) {
    uploadCard.classList.add("hidden");
  }
}

loginForm.addEventListener("submit", async event => {
  event.preventDefault();
  const form = new FormData(loginForm);
  const payload = {
    username: form.get("username"),
    password: form.get("password")
  };
  try {
    await fetchJson("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    loginForm.reset();
    await checkSession();
  } catch (error) {
    alert(error.message);
  }
});

signupForm.addEventListener("submit", async event => {
  event.preventDefault();
  const form = new FormData(signupForm);
  const payload = {
    name: form.get("name"),
    username: form.get("username"),
    password: form.get("password")
  };
  try {
    await fetchJson("/api/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    signupForm.reset();
    await checkSession();
  } catch (error) {
    alert(error.message);
  }
});

uploadForm.addEventListener("submit", async event => {
  event.preventDefault();
  const formData = new FormData(uploadForm);
  try {
    await fetchJson("/api/upload", {
      method: "POST",
      body: formData
    });
    uploadForm.reset();
    await refreshFeed();
  } catch (error) {
    alert(error.message);
  }
});

logoutButton.addEventListener("click", async () => {
  try {
    await fetchJson("/api/logout", { method: "POST" });
    await checkSession();
  } catch (error) {
    console.error(error);
  }
});

refreshFeed();
checkSession();
