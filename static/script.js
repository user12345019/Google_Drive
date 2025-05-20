document.addEventListener("DOMContentLoaded", () => {
  const root = document.documentElement;

  // Toggle "away" class on Ctrl+I
  function toggleAway() {
    root.classList.toggle("away");
  }

  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key.toLowerCase() === "i") {
      event.preventDefault();
      toggleAway();
    }
  });

  // Scroll-to-bottom logic for messages container
  const msgs = document.getElementById("messages");

  function isNearBottom() {
    return msgs.scrollHeight - msgs.scrollTop <= msgs.clientHeight + 100;
  }

  // Initially scroll to bottom
  msgs.scrollTop = msgs.scrollHeight;

  // Observe new messages and auto-scroll if near bottom
  const observer = new MutationObserver(() => {
    if (isNearBottom()) {
      msgs.scrollTop = msgs.scrollHeight;
    }
  });
  observer.observe(msgs, { childList: true });

  // Track manual scrolling
  let shouldScroll = isNearBottom();
  msgs.addEventListener("scroll", () => {
    shouldScroll = isNearBottom();
  });

  // Profile menu toggle
  const profileButton = document.getElementById("profileButton");
  const profileMenu = document.getElementById("profileMenu");
  profileButton.addEventListener("click", (e) => {
    e.stopPropagation();
    profileMenu.classList.toggle("open");
  });
  document.addEventListener("click", () => {
    profileMenu.classList.remove("open");
  });

  // Notifications setup
  const notificationButton = document.getElementById("notificationButton");
  const notificationMenu = document.getElementById("notificationMenu");
  const notificationBadge = document.getElementById("badge");
  const notificationStatus = document.getElementById("notification-status");
  const notificationsList = document.getElementById("notifications");
  let notificationCount = 0;

  function updateTitleWithNotifications(count) {
    if (count > 0) {
      document.title = `(${count}) Home - Google Drive`;
    } else {
      document.title = `Home - Google Drive`;
    }
  }

  updateTitleWithNotifications(notificationCount);

  notificationButton.addEventListener("click", (e) => {
    e.stopPropagation();
    notificationMenu.classList.toggle("open");
    if (notificationMenu.classList.contains("open")) {
      fetch("/mark_notifications_read", { method: "POST" }).then(() => {
        notificationCount = 0;
        updateTitleWithNotifications(notificationCount);
        notificationBadge.textContent = "0";
        notificationBadge.classList.remove("visible");
        notificationStatus.textContent = "No notifications";
      });
    }
  });

  document.addEventListener("click", () => {
    notificationMenu.classList.remove("open");
  });

  function fetchNotifications() {
    fetch("/get_notifications")
      .then((response) => response.json())
      .then((data) => {
        notificationsList.innerHTML = "";
        data.forEach((notification) => {
          const li = document.createElement("li");
          if (notification.type === "private_message" && notification.data) {
            const a = document.createElement("a");
            a.href = `/private_chat/${notification.data.sender_id}`;
            a.textContent = notification.content;
            li.appendChild(a);
          } else {
            li.textContent = notification.content;
          }
          notificationsList.appendChild(li);
        });
        notificationCount = data.length;
        notificationBadge.textContent = notificationCount;
        updateTitleWithNotifications(notificationCount);
        if (notificationCount > 0) {
          notificationBadge.classList.add("visible");
          notificationStatus.textContent = `You have ${notificationCount} new notification${
            notificationCount > 1 ? "s" : ""
          }`;
        } else {
          notificationBadge.classList.remove("visible");
          notificationStatus.textContent = "No notifications";
        }
      });
  }

  // Initialize notifications and start socket
  fetchNotifications();

  const currentUserId = window.currentUserId || null;
  window.socket = io({ transports: ["websocket", "polling"] });

  socket.on("connect", () => {
    if (currentUserId) {
      socket.emit("join", { user_id: currentUserId });
    }
  });

  // Handle new public messages
  socket.on("new_public_message", (data) => {
    const msgElem = document.createElement("p");
    msgElem.innerHTML = `<strong>${data.username}</strong> (${data.timestamp}): ${data.text}`;
    msgs.appendChild(msgElem);
    if (shouldScroll) {
      msgs.scrollTop = msgs.scrollHeight;
    }
  });

  // Handle incoming notifications
  socket.on("new_notification", (notification) => {
    const li = document.createElement("li");
    if (notification.type === "private_message" && notification.data) {
      const a = document.createElement("a");
      a.href = `/private_chat/${notification.data.sender_id}`;
      a.textContent = notification.content;
      li.appendChild(a);
    } else {
      li.textContent = notification.content;
    }
    notificationsList.prepend(li);
    notificationCount++;
    updateTitleWithNotifications(notificationCount);
    notificationBadge.textContent = notificationCount;
    notificationBadge.classList.add("visible");
    notificationStatus.textContent = `You have ${notificationCount} new notification${
      notificationCount > 1 ? "s" : ""
    }`;
  });

  // Clear notifications button
  document
    .getElementById("clearNotifications")
    .addEventListener("click", () => {
      notificationsList.innerHTML = "";
      notificationCount = 0;
      updateTitleWithNotifications(notificationCount);
      notificationBadge.textContent = "0";
      notificationBadge.classList.remove("visible");
      notificationStatus.textContent = "No notifications";
      fetch("/mark_notifications_read", { method: "POST" });
    });
});
