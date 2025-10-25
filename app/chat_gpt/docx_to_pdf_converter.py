# app/utils/docx_to_pdf_converter.py
import os
import subprocess
import shutil
from pathlib import Path
import tempfile
from loguru import logger


def try_win32com(input_path: str, output_path: str) -> bool:
    """
    Windows-only: uses Microsoft Word COM via pywin32.
    FileFormat=17 => PDF
    """
    try:
        import pythoncom
        import win32com.client
    except Exception:
        return False

    try:
        # Init COM properly
        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = None
        try:
            # Open readonly
            doc = word.Documents.Open(input_path, ReadOnly=True)
            # Ensure output directory exists
            out_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(out_dir, exist_ok=True)
            # Save as PDF (17)
            doc.SaveAs(output_path, FileFormat=17)
            logger.info("Converted using win32com (Microsoft Word)")
            return True
        finally:
            if doc is not None:
                doc.Close(False)
            word.Quit()
            pythoncom.CoUninitialize()
    except Exception as e:
        logger.error(f"win32com conversion failed: {e}")
        return False


def try_docx2pdf(input_path: str, output_path: str) -> bool:
    """
    Uses docx2pdf package. On Windows it uses Word COM; on other platforms it may fallback to other methods.
    """
    try:
        from docx2pdf import convert
    except Exception:
        return False

    try:
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        if os.path.isdir(output_path):
            convert(input_path, output_path)
        else:
            with tempfile.TemporaryDirectory() as td:
                convert(input_path, td)
                base = Path(input_path).stem + ".pdf"
                tmp_pdf = Path(td) / base
                if not tmp_pdf.exists():
                    found = list(Path(td).glob("*.pdf"))
                    if not found:
                        raise FileNotFoundError("docx2pdf did not produce a PDF in temporary dir")
                    tmp_pdf = found[0]
                shutil.move(str(tmp_pdf), output_path)
        logger.info("Converted using docx2pdf")
        return True
    except Exception as e:
        logger.error(f"docx2pdf conversion failed: {e}")
        return False


def try_libreoffice(input_path: str, output_path: str) -> bool:
    """
    Uses LibreOffice 'soffice --headless --convert-to pdf --outdir <dir> <file>'
    Works on Linux/macOS/Windows if soffice is in PATH.
    """
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return False

    try:
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, input_path]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        produced = Path(out_dir) / (Path(input_path).stem + ".pdf")
        if not produced.exists():
            matches = list(Path(out_dir).glob("*.pdf"))
            if not matches:
                raise FileNotFoundError("LibreOffice did not produce a PDF in the output directory")
            produced = matches[0]

        if os.path.abspath(produced) != os.path.abspath(output_path):
            shutil.move(str(produced), output_path)

        logger.info("Converted using LibreOffice (soffice)")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"LibreOffice conversion failed: returncode {e.returncode}")
        return False
    except Exception as e:
        logger.error(f"LibreOffice conversion failed: {e}")
        return False


def convert_docx_to_pdf(input_path: str, output_path: str) -> bool:
    """
    Конвертирует DOCX в PDF используя доступные методы
    Возвращает True если успешно, False если не удалось
    """
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(input_path):
        logger.error(f"Input .docx not found: {input_path}")
        return False

    logger.info(f"Converting {input_path} to {output_path}")

    # Try preferred Windows COM method first (if on Windows)
    if os.name == "nt":
        if try_win32com(input_path, output_path):
            return True
        if try_docx2pdf(input_path, output_path):
            return True
        if try_libreoffice(input_path, output_path):
            return True
    else:
        # non-Windows: try LibreOffice first
        if try_libreoffice(input_path, output_path):
            return True
        if try_docx2pdf(input_path, output_path):
            return True

    logger.error("All conversion methods failed")
    return False


def convert_docx_to_pdf_with_fallback(docx_path: str) -> str:
    """
    Конвертирует DOCX в PDF, возвращает путь к PDF файлу.
    Если конвертация не удалась, возвращает путь к исходному DOCX.
    """
    pdf_path = docx_path.replace('.docx', '.pdf')

    if convert_docx_to_pdf(docx_path, pdf_path) and os.path.exists(pdf_path):
        # Удаляем исходный DOCX если PDF создан успешно
        try:
            os.remove(docx_path)
            logger.info(f"Removed original DOCX: {docx_path}")
        except Exception as e:
            logger.warning(f"Could not remove DOCX file: {e}")

        return pdf_path
    else:
        logger.warning(f"PDF conversion failed, keeping DOCX: {docx_path}")
        return docx_path