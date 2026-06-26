// 每日三理 — prototype interactions (vanilla JS, no deps)

// Day-arc tabs on the showcase card
document.querySelectorAll('[data-tabs]').forEach(group => {
  const btns = group.querySelectorAll('.tab-btn');
  const panels = group.querySelectorAll('.tab-panel');
  btns.forEach(btn => btn.addEventListener('click', () => {
    const target = btn.dataset.tab;
    btns.forEach(b => b.classList.toggle('active', b === btn));
    panels.forEach(p => p.classList.toggle('active', p.dataset.panel === target));
  }));
});

// Active-recall: reveal review answer
document.querySelectorAll('.reveal-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const ans = btn.parentElement.querySelector('.review-a');
    const open = ans.classList.toggle('show');
    btn.textContent = open ? '收合答案' : '顯示答案';
  });
});
