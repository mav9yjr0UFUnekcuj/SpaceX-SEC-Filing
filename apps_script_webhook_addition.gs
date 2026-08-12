// ============================================================
// ADD THIS TO YOUR EXISTING Code.gs (the SpaceX SEC Filing
// Monitor script). It does NOT replace anything you already
// have — it reuses your existing sendFilingAlert_() and
// escapeHtml_() functions as-is.
//
// This turns the script into a Web App endpoint that Python
// (running on GitHub Actions) calls whenever it finds a new
// SEC filing. Apps Script still does 100% of the email sending.
// ============================================================

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);

    const expectedSecret =
      PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET");

    if (!expectedSecret || payload.secret !== expectedSecret) {
      return ContentService
        .createTextOutput(JSON.stringify({ error: "Unauthorized" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    sendFilingAlert_({
      accessionNumber: payload.accessionNumber,
      filingDate: payload.filingDate,
      reportDate: payload.reportDate,
      form: payload.form,
      primaryDocument: payload.primaryDocument,
      primaryDocDescription: payload.primaryDocDescription
    });

    return ContentService
      .createTextOutput(JSON.stringify({ status: "sent" }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
