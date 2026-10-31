(() => {
  document.addEventListener('DOMContentLoaded', () => {
    async function post(url) {
      const response = await fetch(url, {
        method: 'POST',
        headers: {'X-CSRFToken': window.getCookie('csrftoken')},
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Не удалось сохранить изменения');
      return result;
    }
    const complete = document.getElementById('complete-project-btn');
    if (complete) complete.addEventListener('click', async () => {
      complete.disabled = true;
      try {
        await post(`/projects/${complete.dataset.id}/complete/`);
        document.querySelector('.project-status-black').textContent = 'Закрыт';
        complete.remove();
        window.toast('Проект завершён');
      } catch (error) {
        window.toast(error.message, {type: 'error'});
        complete.disabled = false;
      }
    });
    const button = document.getElementById('participate-btn');
    if (button) button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        await post(`/projects/${button.dataset.project}/toggle-participate/`);
        // Render the server's current participants, including simultaneous changes.
        window.location.reload();
      } catch (error) {
        window.toast(error.message, {type: 'error'});
        button.disabled = false;
      }
    });
  });
})();
