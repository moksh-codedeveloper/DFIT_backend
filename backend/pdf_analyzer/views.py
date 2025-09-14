import os
import requests
import fitz  # PyMuPDF
import cloudinary
import cloudinary.api as api
import cloudinary.uploader
from dotenv import load_dotenv
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import datetime
from io import BytesIO

# OCR imports (only used if OCR is enabled)
try:
    import pytesseract
    from PIL import Image
    import cv2
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️ OCR dependencies not installed. Only PDF processing will be available.")

# Load environment variables
load_dotenv()

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> dict:
    """Extract text from PDF bytes using PyMuPDF (latest version)"""
    try:
        text = ""
        page_count = 0
        
        # Open PDF from bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = doc.page_count  # Updated property name
        
        for page_num in range(page_count):
            page = doc.load_page(page_num)  # Updated method
            
            # Try multiple text extraction methods for better results
            page_text = ""
            
            # Method 1: Standard text extraction
            page_text = page.get_text("text")  # pyright: ignore[reportAttributeAccessIssue] # Explicitly specify format
            
            # Method 2: If no text found, try with layout preservation
            if not page_text.strip():
                page_text = page.get_text("blocks") # pyright: ignore[reportAttributeAccessIssue]
                if isinstance(page_text, list):
                    page_text = "\n".join([block[4] for block in page_text if len(block) > 4])
            
            # Method 3: If still no text, try dictionary format for more control
            if not page_text.strip():
                text_dict = page.get_text("dict") # pyright: ignore[reportAttributeAccessIssue]
                page_text = ""
                for block in text_dict.get("blocks", []):
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line.get("spans", []):
                                page_text += span.get("text", "") + " "
                            page_text += "\n"
            
            text += f"\n--- Page {page_num + 1} ---\n{page_text}"
        
        doc.close()  # Properly close the document
        
        return {
            "text": text,
            "page_count": page_count,
            "character_count": len(text),
            "word_count": len(text.split()),
            "success": True
        }
    except Exception as e:
        return {
            "text": "",
            "page_count": 0,
            "character_count": 0,
            "word_count": 0,
            "success": False,
            "error": str(e)
        }

def extract_text_from_image_bytes(image_bytes: bytes, filename: str) -> dict:
    """Extract text from image bytes using OCR (Tesseract)"""
    if not OCR_AVAILABLE:
        return {
            "text": "",
            "character_count": 0,
            "word_count": 0,
            "success": False,
            "error": "OCR dependencies not installed"
        }
    
    try:
        # Convert bytes to PIL Image
        image = Image.open(BytesIO(image_bytes))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert PIL image to OpenCV format for preprocessing
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Preprocess image for better OCR results
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Noise removal
        kernel = np.ones((1,1), np.uint8)
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        processed = cv2.medianBlur(processed, 3)
        
        # Convert back to PIL for pytesseract
        processed_image = Image.fromarray(processed)
        
        # Extract text using pytesseract
        text = pytesseract.image_to_string(processed_image, config='--psm 6')
        
        return {
            "text": text.strip(),
            "character_count": len(text.strip()),
            "word_count": len(text.strip().split()),
            "success": True,
            "image_dimensions": f"{image.width}x{image.height}"
        }
        
    except Exception as e:
        return {
            "text": "",
            "character_count": 0,
            "word_count": 0,
            "success": False,
            "error": str(e)
        }

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analyze_and_cleanup_pdfs(request, user_id):
    """
    Process files for a user - PDFs from 'raw' resource type and images from 'image' resource type
    """
    print("🚀 File Analysis and Cleanup started!")
    print(f"📂 Processing files for user: {user_id}")
    
    if OCR_AVAILABLE:
        print("✅ OCR available - will process both PDFs and images")
    else:
        print("⚠️ OCR not available - will only process PDFs")
    
    # Authorization check
    try:
        current_user_id = str(request.user.id)
        if current_user_id != str(user_id):
            return Response({"error": "Unauthorized access"}, status=403)
    except AttributeError:
        return Response({"error": "User authentication error"}, status=401)

    # Configure Cloudinary
    CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    API_KEY = os.getenv("CLOUDINARY_API_KEY")
    API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
    
    if not all([CLOUD_NAME, API_KEY, API_SECRET]):
        return Response({"error": "Cloudinary configuration missing"}, status=500)
    
    cloudinary.config(
        cloud_name=CLOUD_NAME,
        api_key=API_KEY,
        api_secret=API_SECRET,
        secure=True
    )

    try:
        print(f"🔍 Searching for files with prefix: uploads/{user_id}/")

        # ✅ OPTIMIZED: Search PDFs in 'raw' resource type only (since upload is fixed)
        pdf_files = []
        try:
            result_raw = api.resources(
                type="upload",
                prefix=f"uploads/{user_id}/",
                resource_type="raw",  # PDFs are now correctly uploaded here
                max_results=100
            )
            raw_resources = result_raw.get("resources", [])
            
            # Filter for PDFs only
            for file in raw_resources:
                if file.get("format", "").lower() == "pdf":
                    pdf_files.append(file)
            
            print(f"📄 Found {len(pdf_files)} PDFs in 'raw' resource type")
        except Exception as e:
            print(f"⚠️ Error searching raw resources for PDFs: {e}")

        # ✅ OPTIMIZED: Search images in 'image' resource type only (if OCR available)
        image_files = []
        if OCR_AVAILABLE:
            try:
                result_image = api.resources(
                    type="upload",
                    prefix=f"uploads/{user_id}/",
                    resource_type="image",
                    max_results=100
                )
                image_resources = result_image.get("resources", [])
                
                # Filter for supported image formats only
                for file in image_resources:
                    file_format = file.get("format", "").lower()
                    if file_format in ["jpg", "jpeg", "png", "tiff", "bmp", "webp"]:
                        image_files.append(file)
                
                print(f"📄 Found {len(image_files)} processable images in 'image' resource type")
            except Exception as e:
                print(f"⚠️ Error searching image resources: {e}")
        
        print(f"🔍 Total: {len(pdf_files)} PDFs", end="")
        if OCR_AVAILABLE:
            print(f" and {len(image_files)} images")
        else:
            print(" (OCR disabled - ignoring images)")
        
        if not pdf_files and not image_files:
            return Response({
                "error": "No processable files found for this user",
                "user_id": user_id,
                "message": "Upload PDFs" + (" or images" if OCR_AVAILABLE else "") + " first"
            }, status=404)

        # Process files
        processed_files = []
        total_text = ""
        total_pages = 0
        failed_files = []
        deleted_files = []
        
        # ✅ OPTIMIZED: Process PDFs (they should all be in 'raw' resource type now)
        for i, pdf_resource in enumerate(pdf_files):
            public_id = pdf_resource.get("public_id")
            filename = public_id.split("/")[-1]
            resource_type = "raw"  # We know it's raw since we searched in raw resource type
            
            print(f"\n📄 Processing PDF {i+1}/{len(pdf_files)}: {public_id}")
            print(f"🔍 Resource type: {resource_type}")

            try:
                # ✅ FIXED: Build correct URL for raw resource type
                pdf_url = pdf_resource.get("secure_url")
                print(f"🔗 PDF URL: {pdf_url}")
                
                headers = {'User-Agent': 'Django-PDF-Processor/1.0'}
                
                try:
                    response = requests.get(pdf_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    print(f"✅ Direct download successful")
                except requests.exceptions.RequestException as direct_error:
                    print(f"⚠️ Direct download failed: {direct_error}")
                    
                    try:
                        from cloudinary.utils import cloudinary_url
                        signed_url, options = cloudinary_url(
                            public_id,
                            resource_type="raw",
                            sign_url=True,
                            type="upload"  # Use "upload" type, not "authenticated"
                        )
                        print(f"🔐 Trying signed URL: {signed_url}")
                        
                        response = requests.get(signed_url, headers=headers, timeout=30)
                        response.raise_for_status()
                        print(f"✅ Signed URL download successful")
                    except Exception as signed_error:
                        print(f"❌ Signed URL also failed: {signed_error}")
                        raise direct_error

                pdf_bytes = response.content
                print(f"📥 Downloaded PDF into memory: {filename} ({len(pdf_bytes)} bytes)")

                # Verify it's actually a PDF
                if not pdf_bytes.startswith(b'%PDF'):
                    raise Exception("Downloaded content is not a valid PDF file")

                extraction_result = extract_text_from_pdf_bytes(pdf_bytes)
                
                if extraction_result["success"]:
                    print(f"✅ Extracted {extraction_result['character_count']} characters from {extraction_result['page_count']} pages")

                    processed_files.append({
                        "filename": filename,
                        "public_id": public_id,
                        "file_type": "pdf",
                        "resource_type": resource_type,
                        "pages": extraction_result["page_count"],
                        "characters": extraction_result["character_count"],
                        "words": extraction_result["word_count"],
                        "text_preview": extraction_result["text"][:500] + "..." if len(extraction_result["text"]) > 500 else extraction_result["text"],
                        "extraction_method": "PDF parsing (PyMuPDF)"
                    })

                    total_text += f"\n\n=== PDF FILE: {public_id} ===\n{extraction_result['text']}"
                    total_pages += extraction_result["page_count"]

                    # Delete from Cloudinary after successful processing
                    if delete_from_cloudinary(public_id, resource_type):
                        print(f"🗑️ Deleted PDF from Cloudinary: {public_id}")
                        deleted_files.append(public_id)

                else:
                    print(f"❌ Failed to extract text: {extraction_result.get('error')}")
                    failed_files.append({
                        "public_id": public_id,
                        "error": extraction_result.get('error'),
                        "file_type": "pdf"
                    })

            except Exception as e:
                print(f"❌ Error processing PDF {public_id}: {e}")
                failed_files.append({
                    "public_id": public_id,
                    "error": str(e),
                    "file_type": "pdf"
                })

        # ✅ Process images (only if OCR is available)
        if OCR_AVAILABLE:
            for i, image_resource in enumerate(image_files):
                public_id = image_resource.get("public_id")
                filename = public_id.split("/")[-1]
                image_url = image_resource.get("secure_url")
                resource_type = "image"  # We know it's image since we searched in image resource type
                
                print(f"\n🖼️ Processing Image {i+1}/{len(image_files)}: {public_id}")

                try:
                    headers = {'User-Agent': 'Django-PDF-Processor/1.0'}
                    response = requests.get(image_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    
                    image_bytes = response.content
                    print(f"📥 Downloaded image into memory: {filename} ({len(image_bytes)} bytes)")

                    extraction_result = extract_text_from_image_bytes(image_bytes, filename)
                    
                    if extraction_result["success"] and extraction_result["character_count"] > 0:
                        print(f"✅ OCR extracted {extraction_result['character_count']} characters")

                        processed_files.append({
                            "filename": filename,
                            "public_id": public_id,
                            "file_type": "image",
                            "resource_type": resource_type,
                            "image_dimensions": extraction_result.get("image_dimensions", "unknown"),
                            "characters": extraction_result["character_count"],
                            "words": extraction_result["word_count"],
                            "text_preview": extraction_result["text"][:500] + "..." if len(extraction_result["text"]) > 500 else extraction_result["text"],
                            "extraction_method": "OCR (Tesseract)"
                        })

                        total_text += f"\n\n=== IMAGE FILE: {public_id} ===\n{extraction_result['text']}"

                        if delete_from_cloudinary(public_id, resource_type):
                            print(f"🗑️ Deleted image from Cloudinary: {public_id}")
                            deleted_files.append(public_id)

                    else:
                        print(f"⚠️ No text found in image or OCR failed: {extraction_result.get('error', 'No text detected')}")
                        failed_files.append({
                            "public_id": public_id,
                            "error": extraction_result.get('error', 'No text detected'),
                            "file_type": "image"
                        })

                except Exception as e:
                    print(f"❌ Error processing image {public_id}: {e}")
                    failed_files.append({
                        "public_id": public_id,
                        "error": str(e),
                        "file_type": "image"
                    })

        # Return results
        return Response({
            "status": "success",
            "user_id": user_id,
            "summary": {
                "total_pdfs_found": len(pdf_files),
                "total_images_found": len(image_files) if OCR_AVAILABLE else 0,
                "files_processed": len(processed_files),
                "files_failed": len(failed_files),
                "files_deleted_from_cloudinary": len(deleted_files),
                "total_pages_processed": total_pages,
                "total_characters_extracted": len(total_text),
                "ocr_available": OCR_AVAILABLE,
                "processing_timestamp": datetime.now().isoformat()
            },
            "processed_files": processed_files,
            "failed_files": failed_files if failed_files else None,
            "combined_text_preview": total_text[:3000] + "..." if len(total_text) > 3000 else total_text,
            "full_text_available": len(total_text) > 3000,
            "extracted_text": total_text
        })

    except Exception as e:
        print(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            "error": str(e),
            "message": "Critical error during processing"
        }, status=500)


def delete_from_cloudinary(public_id: str, resource_type: str = "image") -> bool:
    """Delete file from Cloudinary with correct resource type"""
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return result.get("result") == "ok"
    except Exception as e:
        print(f"❌ Error deleting {public_id}: {e}")
        return False