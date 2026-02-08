from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
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
    
    def analyze_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        tool_executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """Analyse avec function calling / tools - à implémenter par les providers qui le supportent"""
        # Default implementation: appelle analyze_with_reasoning sans tools
        return self.analyze_with_reasoning(prompt)


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
    
    def analyze_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        tool_executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """Analyse avec function calling"""
        try:
            messages = [
                {"role": "system", "content": "Tu es un expert en infrastructure SD-WAN. Tu as accès à des outils pour récupérer des informations depuis des PDFs de release notes."},
                {"role": "user", "content": prompt}
            ]
            
            tool_calls_log = []
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Appel avec tools
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
                
                message = response.choices[0].message
                messages.append(message)
                
                # Check si le modèle veut appeler des tools
                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        # Exécuter le tool
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        tool_calls_log.append({
                            "iteration": iteration,
                            "tool": function_name,
                            "arguments": function_args
                        })
                        
                        # Exécuter la fonction
                        function_result = tool_executor(function_name, function_args)
                        
                        # Ajouter le résultat aux messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps(function_result, ensure_ascii=False)
                        })
                else:
                    # Pas de tool calls, on a la réponse finale
                    content = message.content
                    
                    # Essayer de parser le JSON
                    try:
                        result = json.loads(content)
                    except:
                        import re
                        json_match = re.search(r'```json\s*({.*?})\s*```', content, re.DOTALL)
                        if json_match:
                            result = json.loads(json_match.group(1))
                        else:
                            try:
                                result = json.loads(content)
                            except:
                                result = {"reasoning": content, "steps": []}
                    
                    # Ajouter les tool calls au résultat
                    result["tool_calls_made"] = tool_calls_log
                    result["iterations"] = iteration
                    
                    return result
            
            # Max iterations atteintes
            return {
                "error": "Max iterations reached",
                "tool_calls_made": tool_calls_log,
                "iterations": iteration
            }
            
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à OpenAI (tools): {str(e)}")


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
    
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
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
    
    def analyze_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        tool_executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """Analyse avec function calling (Groq supporte tools)"""
        try:
            messages = [
                {"role": "system", "content": "Tu es un expert en infrastructure SD-WAN. Tu as accès à des outils pour récupérer des informations depuis des PDFs de release notes."},
                {"role": "user", "content": prompt}
            ]
            
            tool_calls_log = []
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Appel avec tools
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
                
                message = response.choices[0].message
                messages.append(message)
                
                # Check si le modèle veut appeler des tools
                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        # Exécuter le tool
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        tool_calls_log.append({
                            "iteration": iteration,
                            "tool": function_name,
                            "arguments": function_args
                        })
                        
                        # Exécuter la fonction
                        function_result = tool_executor(function_name, function_args)
                        
                        # Ajouter le résultat aux messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps(function_result, ensure_ascii=False)
                        })
                else:
                    # Pas de tool calls, on a la réponse finale
                    content = message.content
                    
                    # Essayer de parser le JSON
                    try:
                        result = json.loads(content)
                    except:
                        import re
                        json_match = re.search(r'```json\s*({.*?})\s*```', content, re.DOTALL)
                        if json_match:
                            result = json.loads(json_match.group(1))
                        else:
                            try:
                                result = json.loads(content)
                            except:
                                result = {"reasoning": content, "steps": []}
                    
                    # Ajouter les tool calls au résultat
                    result["tool_calls_made"] = tool_calls_log
                    result["iterations"] = iteration
                    
                    return result
            
            # Max iterations atteintes
            return {
                "error": "Max iterations reached",
                "tool_calls_made": tool_calls_log,
                "iterations": iteration
            }
            
        except Exception as e:
            raise Exception(f"Erreur lors de l'appel à Groq (tools): {str(e)}")


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
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        return GroqProvider(api_key, model)
    
    else:
        raise Exception(f"Provider LLM non supporté: {provider_name}. Utilisez 'openai', 'grok', 'gemini' ou 'groq'")


def get_analysis_llm_provider() -> LLMProvider:
    """Factory pour obtenir le provider LLM configuré pour l'analyse avec reasoning + function calling"""
    provider_name = os.getenv("ANALYSIS_LLM_PROVIDER", os.getenv("LLM_PROVIDER", "openai")).lower()
    
    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY n'est pas défini dans les variables d'environnement")
        model = os.getenv("ANALYSIS_LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o"))
        return OpenAIProvider(api_key, model)
    
    elif provider_name == "grok":
        api_key = os.getenv("GROK_API_KEY")
        if not api_key:
            raise Exception("GROK_API_KEY n'est pas défini dans les variables d'environnement")
        model = os.getenv("ANALYSIS_LLM_MODEL", os.getenv("GROK_MODEL", "grok-beta"))
        return GrokProvider(api_key, model)
    
    elif provider_name == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise Exception("GEMINI_API_KEY n'est pas défini dans les variables d'environnement")
        model = os.getenv("ANALYSIS_LLM_MODEL", os.getenv("GEMINI_MODEL", "gemini-1.5-pro"))
        return GeminiProvider(api_key, model)
    
    elif provider_name == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise Exception("GROQ_API_KEY n'est pas défini dans les variables d'environnement")
        model = os.getenv("ANALYSIS_LLM_MODEL", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        return GroqProvider(api_key, model)
    
    else:
        raise Exception(f"Provider LLM non supporté: {provider_name}. Utilisez 'openai', 'grok', 'gemini' ou 'groq'")

