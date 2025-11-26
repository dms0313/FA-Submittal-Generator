This application generates permit submittal packages in PDF format and automatically creates table of contents, cover page, and etc.

## AI-Powered Plan Analyzer

This application also includes an AI-powered plan analyzer that can scan uploaded fire alarm plans (PDF or image files) and automatically select the corresponding parts from the list.

### System Dependencies

To use the AI-powered plan analyzer, you will need to install the following system-level dependencies:

*   **Tesseract OCR Engine:** This is used to extract text from the uploaded plan files.
*   **Poppler:** This is used to convert PDF files to images for analysis.

You can install these dependencies on a Debian-based system using the following command:

```bash
sudo apt-get update && sudo apt-get install -y tesseract-ocr poppler-utils
```
