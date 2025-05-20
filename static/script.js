document.addEventListener("DOMContentLoaded", () => {
  // === Shared Variables and Utilities ===
  const root = document.documentElement;
  const msgs = document.getElementById("messages");
  const currentUserId = window.currentUserId || null;
  const otherUserId = window.otherUserId || null; // For private chat

  // Utility Functions
  function escapeHtml(text) {
      const div = document.createElement("div");
      div.innerText = text;
      return div.innerHTML;
  }

  function isNearBottom() {
      return msgs.scrollHeight - msgs.scrollTop <= msgs.clientHeight + 100;
  }

  // === SocketIO Setup ===
  const socket = io({
      transports: ["websocket", "polling"]
  });
  socket.on("connect", () => {
      if (currentUserId) {
          socket.emit("join", {
              user_id: currentUserId
          });
      }
  });

  // === Away Status Toggle ===
  function toggleAway() {
      root.classList.toggle("away");
  }

  document.addEventListener("keydown", (event) => {
      if (event.ctrlKey && event.key.toLowerCase() === "i") {
          event.preventDefault();
          toggleAway();
      }
  });

  // === Profile Menu ===
  const profileButton = document.getElementById("profileButton");
  const profileMenu = document.getElementById("profileMenu");
  if (profileButton) {
      profileButton.addEventListener("click", (e) => {
          e.stopPropagation();
          profileMenu.classList.toggle("open");
      });
  }
  document.addEventListener("click", () => {
      if (profileMenu) profileMenu.classList.remove("open");
  });

  // === Notifications ===
  const notificationButton = document.getElementById("notificationButton");
  const notificationMenu = document.getElementById("notificationMenu");
  const notificationBadge = document.getElementById("badge");
  const notificationStatus = document.getElementById("notification-status");
  const notificationsList = document.getElementById("notifications");
  const clearNotifications = document.getElementById("clearNotifications");
  let notificationCount = 0;

  function updateTitleWithNotifications(count) {
      if (count > 0) {
          document.title = `(${count}) Home - Google Drive`;
      } else {
          document.title = `Home - Google Drive`;
      }
  }

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

  if (notificationButton) {
      notificationButton.addEventListener("click", (e) => {
          e.stopPropagation();
          notificationMenu.classList.toggle("open");
          if (notificationMenu.classList.contains("open")) {
              fetch("/mark_notifications_read", {
                  method: "POST"
              }).then(() => {
                  notificationCount = 0;
                  updateTitleWithNotifications(notificationCount);
                  notificationBadge.textContent = "0";
                  notificationBadge.classList.remove("visible");
                  notificationStatus.textContent = "No notifications";
              });
          }
      });
  }

  if (clearNotifications) {
      clearNotifications.addEventListener("click", () => {
          notificationsList.innerHTML = "";
          notificationCount = 0;
          updateTitleWithNotifications(notificationCount);
          notificationBadge.textContent = "0";
          notificationBadge.classList.remove("visible");
          notificationStatus.textContent = "No notifications";
          fetch("/mark_notifications_read", {
              method: "POST"
          });
      });
  }

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

  // === Public Messages ===
  socket.on("new_public_message", (data) => {
      const msgElem = document.createElement("p");
      msgElem.innerHTML = `<strong>${data.username}</strong> (${data.timestamp}): ${escapeHtml(data.text)}`;
      if (msgs) {
          msgs.appendChild(msgElem);
          if (isNearBottom()) {
              msgs.scrollTop = msgs.scrollHeight;
          }
      }
  });

  // === Private Messages ===
  // === Private Messages ===
  const privateMessagesContainer = document.getElementById("messages");

  // Fetch initial private messages when you load the chat
  function fetchPrivateMessages() {
      if (otherUserId) {
          fetch(`/get_private_messages/${otherUserId}`)
              .then(response => response.json())
              .then(data => {
                  privateMessagesContainer.innerHTML = "";
                  data.forEach(msg => {
                      const msgElement = document.createElement("p");
                      msgElement.innerHTML = `<strong>${escapeHtml(msg.sender)}</strong> (${msg.timestamp}): ${escapeHtml(msg.text)}`;
                      privateMessagesContainer.appendChild(msgElement);
                  });
                  privateMessagesContainer.scrollTop = privateMessagesContainer.scrollHeight;
              });
      }
  }

  // Listen for new private messages in real-time with SocketIO
  socket.on("new_private_message", (msg) => {
      if (msg.sender_id === otherUserId || msg.recipient_id === otherUserId) {
          const msgElement = document.createElement("p");
          const sender = msg.sender_id === currentUserId ? "You" : escapeHtml(msg.sender_username);
          msgElement.innerHTML = `<strong>${sender}</strong> (${msg.timestamp}): ${escapeHtml(msg.text)}`;
          privateMessagesContainer.appendChild(msgElement);
          privateMessagesContainer.scrollTop = privateMessagesContainer.scrollHeight; // Auto-scroll to the bottom
      }
  });

  // Load initial messages (no polling needed after this)
  if (otherUserId) {
      fetchPrivateMessages();
  }

  // === Users List ===
  function fetchUsersList() {
      fetch("/get_users")
          .then((response) => response.json())
          .then((data) => {
              const usersList = document.getElementById("users")?.querySelector("ul");
              if (usersList) {
                  usersList.innerHTML = "";
                  data.forEach((user) => {
                      const li = document.createElement("li");
                      const a = document.createElement("a");
                      a.href = `/private_chat/${user.id}`;
                      a.textContent = user.username;
                      li.appendChild(a);
                      usersList.appendChild(li);
                  });
              }
          });
  }

  // === Scroll-to-Bottom Logic ===
  if (msgs) {
      msgs.scrollTop = msgs.scrollHeight;
      const observer = new MutationObserver(() => {
          if (isNearBottom()) {
              msgs.scrollTop = msgs.scrollHeight;
          }
      });
      observer.observe(msgs, {
          childList: true
      });
      msgs.addEventListener("scroll", () => {
          shouldScroll = isNearBottom();
      });
  }

  // === Initialization ===
  fetchNotifications();
  setInterval(fetchNotifications, 1000);
  fetchUsersList();
  setInterval(fetchUsersList, 1000);
});