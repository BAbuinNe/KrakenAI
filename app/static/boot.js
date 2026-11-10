/* The server decides whether local or cloud AI is configured.
   Never overwrite the status label after /api/me confirms it. */
document.addEventListener('DOMContentLoaded',()=>{
  const upload=document.getElementById('railUpload');
  if(upload)upload.setAttribute('aria-label','Загрузить ТЗ и коммерческие предложения');
});
