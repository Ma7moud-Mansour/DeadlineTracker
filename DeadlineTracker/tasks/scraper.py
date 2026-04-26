from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def run_msa_scraper(student_id, student_password):
    login_url = "https://e-learning.msa.edu.eg/login/index.php"
    tasks_url = "https://e-learning.msa.edu.eg/my/"
    
    extracted_tasks = []
    driver = None

    try:
        # ==========================================
        # إعدادات الـ VPS (Headless Chrome)
        # ==========================================
        chrome_options = Options()
        chrome_options.add_argument("--headless") # تشغيل مخفي بدون واجهة رسومية
        chrome_options.add_argument("--no-sandbox") # ضروري جداً لسيرفرات لينكس
        chrome_options.add_argument("--disable-dev-shm-usage") # بيمنع الكراش بسبب الميموري
        chrome_options.add_argument("--window-size=1920,1080") # بنوهم الموقع إنه فاتح من شاشة كاملة
        
        # بنشغل كروم بالإعدادات الجديدة
        driver = webdriver.Chrome(options=chrome_options)
        # ==========================================
        
        driver.get(login_url)
        
        # إدخال بيانات الطالب
        driver.find_element(By.ID, "username").send_keys(student_id)
        driver.find_element(By.ID, "password").send_keys(student_password)
        driver.find_element(By.ID, "loginbtn").click()

        time.sleep(3) 
        driver.get(tasks_url) 
        
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-region='event-list-item']"))
        )
        
        tasks = driver.find_elements(By.CSS_SELECTOR, "[data-region='event-list-item']")
        
        for task in tasks:
            try:
                task_name = task.find_element(By.CSS_SELECTOR, ".event-name a").text
                course_info = task.find_element(By.CSS_SELECTOR, ".event-name-container small").text
                due_time = task.find_element(By.CSS_SELECTOR, ".timeline-name small.text-end").text
                date_header = task.find_element(By.XPATH, "./ancestor::div[contains(@class, 'list-group')]/preceding-sibling::div[@data-region='event-list-content-date'][1]").text
                
                extracted_tasks.append({
                    "title": task_name,
                    "course": course_info,
                    "due_date": f"{date_header} - {due_time}"
                })
            except Exception:
                continue

        return True, extracted_tasks 

    except Exception as e:
        # لو حصل إيرور هنرجعه لجانجو عشان يطبعه لليوزر
        return False, str(e)

    finally:
        if driver:
            driver.quit()