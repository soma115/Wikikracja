tinymce.init({
  selector: 'textarea',

  skin: 'oxide-dark',
  content_css: '/static/home/css/tailwind.build.css',
  body_class: 'tw-post-content',

  menubar: false,
  toolbar_mode: 'sliding',
  mobile: {
    toolbar_mode: 'floating'
  },
  resize: true,
  height: 500,

  image_title: false,
  image_caption: false,
  automatic_uploads: true,
  image_advtab: false,
  file_picker_types: "image media",

  images_upload_handler: function(blobInfo, progress) {
    var formData = new FormData();
    formData.append('images', blobInfo.blob(), blobInfo.filename());
    return window.apiFetch('/chat/upload/', {
      method: 'POST',
      body: formData
    }).then(function(response) {
      return response.json().then(function(data) {
        if (!response.ok || !data.filenames || !data.filenames[0]) {
          throw new Error(data.error || 'Image upload failed');
        }
        progress(100);
        return '/media/uploads/' + encodeURIComponent(data.filenames[0]);
      });
    });
  },

  plugins: "advlist anchor autolink autosave codesample fullscreen image importcss link lists media nonbreaking searchreplace table code",

  toolbar: "fullscreen | undo redo | blocks | forecolor bold italic underline strikethrough codesample removeformat | alignjustify alignleft aligncenter alignright | numlist bullist | table image | anchor link | code searchreplace",

  file_picker_callback: function(cb, value, meta) {
    var input = document.createElement("input");
    input.setAttribute("type", "file");
    if (meta.filetype == "image") {
      input.setAttribute("accept", "image/*");
    }
    if (meta.filetype == "media") {
      input.setAttribute("accept", "video/*");
    }

    input.onchange = function() {
      var file = this.files[0];
      var reader = new FileReader();
      reader.onload = function() {
        var id = "blobid" + (new Date()).getTime();
        var blobCache = tinymce.activeEditor.editorUpload.blobCache;
        var base64 = reader.result.split(",")[1];
        var blobInfo = blobCache.create(id, file, base64);
        blobCache.add(blobInfo);
        cb(blobInfo.blobUri(), { title: file.name });
      };
      reader.readAsDataURL(file);
    };
    input.click();
  }
});

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function initAttachmentUploader(container) {
  const input = container.querySelector('.tw-file-upload-input');
  const list = container.parentElement.querySelector('[data-file-upload-list]');
  const error = container.parentElement.querySelector('[data-file-upload-error]');
  if (!input || !list || !error) return;

  let selectedFiles = Array.from(input.files || []);
  const maxBytes = Number(container.dataset.maxSizeMb || 0) * 1_000_000;
  const maxSizeError = container.dataset.maxSizeError || '';
  const removeLabel = container.dataset.removeLabel || 'Remove file';
  const previewLabel = container.dataset.previewLabel || 'Selected image';
  const singleFile = container.hasAttribute('data-file-upload-single');
  const currentFile = container.parentElement.querySelector('[data-file-upload-current]');

  function fileKey(file) {
    return `${file.name}:${file.size}:${file.lastModified}`;
  }

  function syncInput() {
    if (typeof DataTransfer === 'undefined') return;
    const transfer = new DataTransfer();
    selectedFiles.forEach(file => transfer.items.add(file));
    input.files = transfer.files;
  }

  function renderFiles() {
    list.replaceChildren();
    selectedFiles.forEach((file, index) => {
      const item = document.createElement('div');
      item.className = 'tw-file-upload-item';
      const isImage = singleFile || file.type.startsWith('image/');
      if (isImage) {
        const preview = document.createElement('img');
        preview.className = 'tw-file-upload-preview';
        preview.alt = `${previewLabel}: ${file.name}`;
        const reader = new FileReader();
        reader.addEventListener('load', () => {
          preview.src = reader.result;
        });
        reader.readAsDataURL(file);
        item.append(preview);
      } else {
        const icon = document.createElement('i');
        icon.className = 'fas fa-paperclip fa-fw tw-text-accent';
        icon.setAttribute('aria-hidden', 'true');
        item.append(icon);
      }
      const name = document.createElement('span');
      name.className = 'tw-file-upload-name';
      name.textContent = file.name;
      const size = document.createElement('span');
      size.className = 'tw-file-upload-size';
      size.textContent = formatFileSize(file.size);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'tw-btn tw-btn-sm tw-btn-secondary';
      remove.dataset.fileIndex = index;
      remove.title = removeLabel;
      remove.setAttribute('aria-label', `${removeLabel}: ${file.name}`);
      remove.innerHTML = '<i class="fas fa-times fa-fw" aria-hidden="true"></i>';
      item.append(name, size, remove);
      list.append(item);
    });
  }

  function addFiles(files) {
    const rejected = [];
    const known = new Set(selectedFiles.map(fileKey));
    const filesToAdd = singleFile ? Array.from(files).slice(0, 1) : Array.from(files);
    if (singleFile) selectedFiles = [];
    filesToAdd.forEach(file => {
      if (maxBytes && file.size > maxBytes) {
        rejected.push(file.name);
      } else if (!known.has(fileKey(file)) || singleFile) {
        selectedFiles.push(file);
        known.add(fileKey(file));
      }
    });
    error.hidden = rejected.length === 0;
    error.textContent = rejected.length ? `${maxSizeError} (${rejected.join(', ')})` : '';
    if (currentFile) currentFile.hidden = selectedFiles.length > 0;
    syncInput();
    renderFiles();
  }

  input.addEventListener('change', event => addFiles(event.target.files));
  container.addEventListener('dragover', event => {
    event.preventDefault();
    container.classList.add('tw-file-upload--active');
  });
  container.addEventListener('dragleave', event => {
    if (!container.contains(event.relatedTarget)) container.classList.remove('tw-file-upload--active');
  });
  container.addEventListener('drop', event => {
    event.preventDefault();
    container.classList.remove('tw-file-upload--active');
    addFiles(event.dataTransfer.files);
  });
  list.addEventListener('click', event => {
    const button = event.target.closest('[data-file-index]');
    if (!button) return;
    selectedFiles.splice(Number(button.dataset.fileIndex), 1);
    if (currentFile) currentFile.hidden = selectedFiles.length > 0;
    syncInput();
    renderFiles();
  });

  syncInput();
  renderFiles();
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-file-upload]').forEach(initAttachmentUploader);
});
