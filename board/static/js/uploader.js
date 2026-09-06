tinymce.init({
  selector: 'textarea',

  skin: 'oxide-dark',
  content_css: 'dark',

  menubar: false,
  toolbar_mode: 'sliding',
  resize: true,
  height: 500,

  image_title: false,
  image_caption: false,
  automatic_uploads: false,
  image_advtab: false,
  file_picker_types: "image media",

  images_upload_url: 'uploads/',

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
  },
  content_style: "body { font-family:Helvetica,Arial,sans-serif; font-size:14px }"
});
