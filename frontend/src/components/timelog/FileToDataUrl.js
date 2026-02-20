
//파일(이미지)을 base64 데이터 URL로 바꿔주는 유틸 함수

export function FileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file) return reject(new Error("No file"));
    if (!file.type?.startsWith("image/")) return reject(new Error("Not an image"));

    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("FileReader error"));
    reader.readAsDataURL(file);
  });
}
