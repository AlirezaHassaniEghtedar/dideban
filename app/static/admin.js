async function send(path, method, data) {
  const feedback = document.getElementById("feedback");
  try {
    const response = await fetch(path, {method, headers: {"Content-Type":"application/json"}, body: data && JSON.stringify(data)});
    if (response.ok) location.reload();
    else feedback.textContent = "درخواست ثبت نشد (" + response.status + "). اطلاعات را بررسی کنید.";
  } catch { feedback.textContent = "ارتباط برقرار نشد. دوباره تلاش کنید."; }
}
document.getElementById("add").addEventListener("submit", e => {
  e.preventDefault();
  send("/api/admin/sources", "POST", Object.fromEntries(new FormData(e.target)));
});
document.addEventListener("click", e => {
  const b = e.target.closest("button[data-action]");
  if (!b) return;
  if (b.dataset.action === "approve") send("/api/admin/sources", "POST", {name:b.dataset.name,url:b.dataset.url});
  else if (b.dataset.action === "queue") send("/api/admin/crawl/" + b.dataset.id, "POST");
  else send("/api/admin/opportunities/" + b.dataset.id, "PATCH", {decision:b.dataset.action,digest:b.dataset.digest});
});
