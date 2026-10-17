import random

class ai4artsed_random_language_selector:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {}
        }

    RETURN_TYPES = tuple(["STRING"] * 12)
    RETURN_NAMES = tuple([f"language_{i+1}" for i in range(12)])
    FUNCTION = "select_languages"
    CATEGORY = "AI4ArtsEd"
    def select_languages(self):
        supported_languages = [
            "English", "Mandarin Chinese", "Hindi", "Spanish", "French", "Arabic",
            "Bengali", "Russian", "Portuguese", "Indonesian", "Urdu", "German",
            "Japanese", "Swahili", "Turkish", "Korean",
            "Tamil", "Vietnamese", "Italian", "Persian", 
            "Hausa",    
            "Ukrainian", "Igbo", 
            "Kurdish", "Somali",
            "Malay", "Lao", "Kinyarwanda",
            "Czech", "Greek", "Hungarian", "Kazakh",
            "Xhosa", "Yoruba", 
            "Thai", "Polish",
            "Dutch", "Romanian", "Serbo-Croatian", "Malagasy",
            "Hebrew", "Swedish", "Danish", "Norwegian", "Finnish", "Bulgarian",
            "Slovak", "Lithuanian", "Latvian"
        ]
        selected_languages = random.sample(supported_languages, 12)
        return tuple(selected_languages)
