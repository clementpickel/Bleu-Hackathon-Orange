from abc import ABC, abstractmethod
from typing import Dict, Any
import os
import json


class LLMProvider(ABC):
    """Classe abstraite pour les providers LLM"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    @abstractmethod
    def extract_info(self, text: str, prompt: str) -> Dict[str, Any]:
        """Extrait les informations structurées d'un texte avec un prompt personnalisé"""
        pass
    
    @abstractmethod
    def analyze_text(self, prompt: str) -> str:
        """Analyse un texte et retourne une réponse textuelle (non-JSON)"""
        pass
    
    @abstractmethod
    def analyze_with_reasoning(self, prompt: str) -> Dict[str, Any]:
        """Analyse avec réflexion profonde, retourne JSON structuré avec raisonnement"""
        pass


class OpenAIProvider(LLMProvider):
    """Provider pour OpenAI"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        super().__init__(api_key)
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def extract_info(self, text: str, prompt: str) -> Dict[str, Any]:
        """Extrait les informations avec un prompt personnalisé"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un assistant qui extrait des informations structurées de documents techniques."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à OpenAI: {str(e)}")
    
    def analyze_text(self, prompt: str) -> str:
        """Analyse un texte et retourne une réponse textuelle"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en infrastructure SD-WAN et en gestion de versions logicielles."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à OpenAI: {str(e)}")
    
    def analyze_with_reasoning(self, prompt: str) -> Dict[str, Any]:
        """Analyse avec réflexion profonde (utilise o1-mini)"""
        try:
            # Utiliser o1-mini pour raisonnement complexe
            response = self.client.chat.completions.create(
                model="o1-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.choices[0].message.content
            # Extraire le JSON de la réponse
            import re
            json_match = re.search(r'```json\s*({.*?})\s*```', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Essayer de parser directement
                try:
                    result = json.loads(content)
                except:
                    # Si échec, parser comme markdown
                    result = {"reasoning": content, "steps": []}
            
            return result
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à OpenAI (reasoning): {str(e)}")


class GrokProvider(LLMProvider):
    """Provider pour Grok (xAI)"""
    
    def __init__(self, api_key: str, model: str = "grok-beta"):
        super().__init__(api_key)
        from openai import OpenAI
        # Grok utilise l'API compatible OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )
        self.model = model
    
    def extract_info(self, text: str, prompt: str) -> Dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un assistant qui extrait des informations structurées de documents techniques."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            # Grok peut retourner le JSON directement ou avec du texte
            content = response.choices[0].message.content
            
            # Essayer de parser directement
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Si échec, chercher le JSON dans le texte
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise Exception("Impossible de parser la réponse JSON")
            
            return result
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Grok: {str(e)}")
    
    def analyze_text(self, prompt: str) -> str:
        """Analyse un texte et retourne une réponse textuelle"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en infrastructure SD-WAN et en gestion de versions logicielles."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Grok: {str(e)}")
    
    def analyze_with_reasoning(self, prompt: str) -> Dict[str, Any]:
        """Analyse avec réflexion (Grok utilise temperature élevée pour simulation)"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en infrastructure SD-WAN. Analyse en profondeur et retourne un JSON structuré."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            content = response.choices[0].message.content
            import re
            json_match = re.search(r'```json\s*({.*?})\s*```', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                try:
                    result = json.loads(content)
                except:
                    result = {"reasoning": content, "steps": []}
            
            return result
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Grok (reasoning): {str(e)}")


class GeminiProvider(LLMProvider):
    """Provider pour Google Gemini"""
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        super().__init__(api_key)
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
    
    def extract_info(self, text: str, prompt: str) -> Dict[str, Any]:
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json"
                }
            )
            
            # Gemini retourne le texte JSON
            content = response.text
            
            # Parser le JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Si échec, chercher le JSON dans le texte
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise Exception("Impossible de parser la réponse JSON")
            
            return result
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Gemini: {str(e)}")
    
    def analyze_text(self, prompt: str) -> str:
        """Analyse un texte et retourne une réponse textuelle"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"temperature": 0.3}
            )
            return response.text
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Gemini: {str(e)}")
    
    def analyze_with_reasoning(self, prompt: str) -> Dict[str, Any]:
        """Analyse avec réflexion profonde (Gemini 1.5 Pro avec thinking)"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.5,
                    "response_mime_type": "application/json"
                }
            )
            
            content = response.text
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {"reasoning": content, "steps": []}
            
            return result
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Gemini (reasoning): {str(e)}")


class GroqProvider(LLMProvider):
    """Provider pour Groq (inférence rapide)"""
    
    def __init__(self, api_key: str, model: str = "llama-3.1-70b-versatile"):
        super().__init__(api_key)
        from openai import OpenAI
        # Groq utilise l'API compatible OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = model
    
    def extract_info(self, text: str, prompt: str) -> Dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un assistant qui extrait des informations structurées de documents techniques."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            # Groq retourne le JSON
            content = response.choices[0].message.content
            
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Si échec, chercher le JSON dans le texte
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise Exception("Impossible de parser la réponse JSON")
            
            return result
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Groq: {str(e)}")
    
    def analyze_text(self, prompt: str) -> str:
        """Analyse un texte et retourne une réponse textuelle"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en infrastructure SD-WAN et en gestion de versions logicielles."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Groq: {str(e)}")
    
    def analyze_with_reasoning(self, prompt: str) -> Dict[str, Any]:
        """Analyse avec réflexion (Groq avec llama-3.1)"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un expert en infrastructure SD-WAN. Analyse en profondeur et retourne un JSON structuré."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {"reasoning": content, "steps": []}
            
            return result
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Groq (reasoning): {str(e)}")


def get_llm_provider() -> LLMProvider:
    """Factory pour obtenir le provider LLM configuré"""
    provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY n'est pas défini dans les variables d'environnement")
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return OpenAIProvider(api_key, model)
    
    elif provider_name == "grok":
        api_key = os.getenv("GROK_API_KEY")
        if not api_key:
            raise Exception("GROK_API_KEY n'est pas défini dans les variables d'environnement")
        model = os.getenv("GROK_MODEL", "grok-beta")
        return GrokProvider(api_key, model)
    
    elif provider_name == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise Exception("GEMINI_API_KEY n'est pas défini dans les variables d'environnement")
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        return GeminiProvider(api_key, model)
    
    elif provider_name == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise Exception("GROQ_API_KEY n'est pas défini dans les variables d'environnement")
        model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
        return GroqProvider(api_key, model)
    
    else:
        raise Exception(f"Provider LLM non supporté: {provider_name}. Utilisez 'openai', 'grok', 'gemini' ou 'groq'")
