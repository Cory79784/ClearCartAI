const podId = process.env.RUNPOD_POD_ID || process.env.POD_ID;

console.log("Frontend local URL: http://localhost:3000");
if (podId) {
  console.log(`Frontend RunPod proxy URL: https://${podId}-3000.proxy.runpod.net`);
} else {
  console.log("Frontend RunPod proxy URL: unavailable (RUNPOD_POD_ID not set)");
}
