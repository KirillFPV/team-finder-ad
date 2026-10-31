// Profile skills: all mutations use the session CSRF token and safe text nodes.
(() => {
  document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('skills-container');
    const addButton = document.getElementById('add-skill-btn');
    if (!container || !addButton) return;
    const wrapper = document.getElementById('skill-input-wrapper');
    const input = document.getElementById('skill-input');
    const suggestions = document.getElementById('skill-suggestions');
    const base = `/users/${container.dataset.userId}/skills/`;
    let timer;
    let generation = 0;
    let busy = false;
    input.maxLength = 124;
    input.setAttribute('aria-label', 'Название навыка');

    const showError = error => window.toast(error.message || 'Ошибка сети', {type: 'error'});
    async function request(url, data) {
      const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.getCookie('csrftoken')},
        body: JSON.stringify(data),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Не удалось сохранить навык');
      return result;
    }
    function hideInput() {
      clearTimeout(timer);
      generation++;
      wrapper.classList.add('hidden');
      suggestions.classList.add('hidden');
      addButton.classList.remove('hidden');
    }
    function updateEmpty() {
      const empty = container.querySelector('.skill-empty');
      const hasSkills = !!container.querySelector('.skill-chip');
      if (hasSkills && empty) empty.remove();
      if (!hasSkills && !empty) {
        const label = document.createElement('span');
        label.className = 'skill-empty';
        label.textContent = 'Навыки не указаны';
        container.insertBefore(label, addButton);
      }
    }
    function appendChip(skill) {
      if (container.querySelector(`.skill-chip[data-id="${skill.id}"]`)) return;
      const chip = document.createElement('span');
      chip.className = 'skill-chip';
      chip.dataset.id = skill.id;
      chip.append(document.createTextNode(skill.name + ' '));
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'remove-skill-btn';
      remove.setAttribute('aria-label', `Удалить навык ${skill.name}`);
      remove.textContent = '×';
      chip.append(remove);
      container.insertBefore(chip, addButton);
      updateEmpty();
    }
    async function addSkill(data) {
      if (busy) return;
      busy = true;
      try {
        appendChip(await request(base + 'add/', data));
        hideInput();
      } catch (error) {
        showError(error);
      } finally {
        busy = false;
      }
    }
    addButton.addEventListener('click', () => {
      addButton.classList.add('hidden');
      wrapper.classList.remove('hidden');
      input.value = '';
      suggestions.replaceChildren();
      suggestions.classList.add('hidden');
      input.focus();
    });
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const current = ++generation;
      const query = input.value.trim();
      suggestions.replaceChildren();
      suggestions.classList.add('hidden');
      if (!query) return;
      timer = setTimeout(async () => {
        try {
          const response = await fetch(`/users/skills/?q=${encodeURIComponent(query)}`);
          if (!response.ok) throw new Error('Не удалось загрузить подсказки');
          const skills = await response.json();
          if (generation !== current) return;
          suggestions.replaceChildren();
          skills.forEach(skill => {
            const item = document.createElement('li');
            item.textContent = skill.name;
            item.dataset.id = skill.id;
            item.dataset.name = skill.name;
            suggestions.append(item);
          });
          if (!skills.some(skill => skill.name.toLowerCase() === query.toLowerCase())) {
            const item = document.createElement('li');
            item.className = 'create-new';
            item.textContent = `Создать «${query}»`;
            item.dataset.name = query;
            suggestions.append(item);
          }
          suggestions.classList.remove('hidden');
        } catch (error) {
          if (generation === current) showError(error);
        }
      }, 200);
    });
    suggestions.addEventListener('mousedown', event => {
      const item = event.target.closest('li');
      if (!item) return;
      event.preventDefault();
      addSkill(item.dataset.id ? {skill_id: Number(item.dataset.id)} : {name: item.dataset.name});
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') hideInput();
      if (event.key === 'Enter' && input.value.trim()) {
        event.preventDefault();
        const query = input.value.trim();
        const exact = [...suggestions.children].find(item =>
          item.dataset.id && item.dataset.name.toLowerCase() === query.toLowerCase());
        addSkill(exact ? {skill_id: Number(exact.dataset.id)} : {name: query});
      }
    });
    input.addEventListener('blur', () => { if (!busy) hideInput(); });
    container.addEventListener('click', async event => {
      const button = event.target.closest('.remove-skill-btn');
      if (!button || button.disabled) return;
      const chip = button.closest('.skill-chip');
      button.disabled = true;
      try {
        await request(base + `${chip.dataset.id}/remove/`, {});
        chip.remove();
        updateEmpty();
      } catch (error) {
        showError(error);
        button.disabled = false;
      }
    });
  });
})();
