// ComfyUI-usgromana admin panel
// Minimal, dependency-free UI that talks to /usgromana/api/*
// NOTE: For now this panel is only callable from localhost (enforced server-side).

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

async function loadUsers() {
  const root = document.getElementById('usgromana-admin-root');
  const tableBody = root.querySelector('tbody[data-role="users-body"]');
  tableBody.innerHTML = '<tr><td colspan="7">Loading…</td></tr>';
  try {
    const data = await api('/usgromana/api/users');
    const users = data.users || [];
    if (!users.length) {
      tableBody.innerHTML =
        '<tr><td colspan="7">No users yet. The default admin account is <code>admin / admin</code> – please change it.</td></tr>';
      return;
    }
    tableBody.innerHTML = '';
    for (const u of users) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${u.username}</td>
        <td><input type="checkbox" data-field="is_admin" ${u.is_admin ? 'checked' : ''}></td>
        <td><input type="text" data-field="groups" value="${(u.groups || []).join(', ')}"></td>
        <td>
          <label><input type="checkbox" data-perm="can_manage_users" ${u.permissions?.can_manage_users ? 'checked' : ''}> manage users</label><br>
          <label><input type="checkbox" data-perm="can_use_gallery" ${u.permissions?.can_use_gallery ? 'checked' : ''}> use gallery</label><br>
          <label><input type="checkbox" data-perm="can_change_theme" ${u.permissions?.can_change_theme ? 'checked' : ''}> change theme</label>
        </td>
        <td><input type="text" data-field="theme" value="${u.theme || ''}" placeholder="optional"></td>
        <td><input type="text" data-field="gallery_root" value="${u.gallery_root || ''}" placeholder="optional absolute path"></td>
        <td>
          <button data-action="save">Save</button>
          <button data-action="delete">Delete</button>
        </td>
      `;
      tr.dataset.username = u.username;
      tableBody.appendChild(tr);
    }
  } catch (err) {
    console.error(err);
    tableBody.innerHTML = `<tr><td colspan="7">Failed to load users: ${err.message}</td></tr>`;
  }
}

function attachHandlers() {
  const root = document.getElementById('usgromana-admin-root');
  const form = root.querySelector('form[data-role="create-user"]');
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    const payload = {
      username: fd.get('username')?.trim(),
      password: fd.get('password') || '',
      is_admin: fd.get('is_admin') === 'on',
      groups: (fd.get('groups') || '').split(',').map(s => s.trim()).filter(Boolean),
      permissions: {
        can_manage_users: fd.get('can_manage_users') === 'on',
        can_use_gallery: fd.get('can_use_gallery') === 'on',
        can_change_theme: fd.get('can_change_theme') === 'on',
      },
      theme: fd.get('theme') || null,
      gallery_root: fd.get('gallery_root') || null,
    };
    try {
      await api('/usgromana/api/users', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      form.reset();
      await loadUsers();
    } catch (err) {
      alert('Failed to create user: ' + err.message);
    }
  });

  const tableBody = root.querySelector('tbody[data-role="users-body"]');
  tableBody.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('button[data-action]');
    if (!btn) return;
    const tr = btn.closest('tr[data-username]');
    const username = tr?.dataset.username;
    if (!username) return;

    if (btn.dataset.action === 'delete') {
      if (!confirm(`Delete user "${username}"?`)) return;
      try {
        await api(`/usgromana/api/users/${encodeURIComponent(username)}`, {
          method: 'DELETE',
        });
        await loadUsers();
      } catch (err) {
        alert('Failed to delete user: ' + err.message);
      }
      return;
    }

    if (btn.dataset.action === 'save') {
      const payload = {};
      // admin flag
      const isAdmin = tr.querySelector('input[data-field="is_admin"]');
      payload.is_admin = !!isAdmin?.checked;

      // groups
      const groupsInput = tr.querySelector('input[data-field="groups"]');
      payload.groups = (groupsInput?.value || '').split(',').map(s => s.trim()).filter(Boolean);

      // permissions
      const perms = {};
      tr.querySelectorAll('input[data-perm]').forEach((el) => {
        perms[el.dataset.perm] = el.checked;
      });
      payload.permissions = perms;

      // theme & gallery root
      const themeInput = tr.querySelector('input[data-field="theme"]');
      const galleryInput = tr.querySelector('input[data-field="gallery_root"]');
      payload.theme = themeInput?.value || null;
      payload.gallery_root = galleryInput?.value || null;

      try {
        await api(`/usgromana/api/users/${encodeURIComponent(username)}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        await loadUsers();
      } catch (err) {
        alert('Failed to save user: ' + err.message);
      }
    }
  });
}

function renderShell() {
  const root = document.getElementById('Usgromana-admin-root');
  root.innerHTML = `
    <section style="margin-bottom: 1.5rem; padding: 1rem; border-radius: 0.75rem; background: #1b1b1b; border: 1px solid #333;">
      <h2 style="margin-top: 0; font-size: 1.2rem;">Create user</h2>
      <form data-role="create-user" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; align-items: flex-end;">
        <label>Username<br><input name="username" required></label>
        <label>Password<br><input name="password" type="password" required></label>
        <label>Groups (comma-separated)<br><input name="groups" placeholder="admins, artists"></label>
        <div>
          <strong>Permissions</strong><br>
          <label><input type="checkbox" name="is_admin"> Admin</label><br>
          <label><input type="checkbox" name="can_manage_users" checked> Manage users</label><br>
          <label><input type="checkbox" name="can_use_gallery" checked> Use gallery</label><br>
          <label><input type="checkbox" name="can_change_theme" checked> Change theme</label>
        </div>
        <label>Theme override<br><input name="theme" placeholder="optional theme id"></label>
        <label>Gallery root<br><input name="gallery_root" placeholder="optional absolute path"></label>
        <div>
          <button type="submit">Create</button>
        </div>
      </form>
    </section>
    <section style="padding: 1rem; border-radius: 0.75rem; background: #1b1b1b; border: 1px solid #333;">
      <h2 style="margin-top: 0; font-size: 1.2rem;">Users</h2>
      <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
        <thead>
          <tr>
            <th style="text-align:left; border-bottom: 1px solid #333; padding: 0.25rem 0.4rem;">Username</th>
            <th style="text-align:left; border-bottom: 1px solid #333; padding: 0.25rem 0.4rem;">Admin</th>
            <th style="text-align:left; border-bottom: 1px solid #333; padding: 0.25rem 0.4rem;">Groups</th>
            <th style="text-align:left; border-bottom: 1px solid #333; padding: 0.25rem 0.4rem;">Permissions</th>
            <th style="text-align:left; border-bottom: 1px solid #333; padding: 0.25rem 0.4rem;">Theme</th>
            <th style="text-align:left; border-bottom: 1px solid #333; padding: 0.25rem 0.4rem;">Gallery root</th>
            <th style="text-align:left; border-bottom: 1px solid #333; padding: 0.25rem 0.4rem;">Actions</th>
          </tr>
        </thead>
        <tbody data-role="users-body">
          <tr><td colspan="7">Loading…</td></tr>
        </tbody>
      </table>
    </section>
  `;
}

document.addEventListener('DOMContentLoaded', async () => {
  renderShell();
  attachHandlers();
  await loadUsers();
});
