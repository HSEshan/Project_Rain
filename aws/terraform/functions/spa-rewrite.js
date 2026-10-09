// CloudFront Function, viewer-request, on the frontend (default) behaviour only.
//
// The app is a single-page app: /dm/123 is a route React Router draws, not a
// file in the bucket. Without this, a reload on any deep link asks S3 for an
// object named "dm/123", and the private bucket answers 403.
//
// The usual fix, a distribution-wide "custom error response" mapping 403/404
// to /index.html, would be wrong here: it applies to every behaviour, so a
// 404 from /api (which this API uses to mean "not a member") would come back
// as a 200 HTML page. Rewriting only in this behaviour leaves the API alone.
//
// Rule: a last path segment with no dot is a route, so serve the app shell.
// Anything with an extension (/assets/index-3f2a.js, /favicon.svg) is a real
// file and passes through.
function handler(event) {
  var request = event.request;
  var last = request.uri.split("/").pop();
  if (last.indexOf(".") === -1) {
    request.uri = "/index.html";
  }
  return request;
}
