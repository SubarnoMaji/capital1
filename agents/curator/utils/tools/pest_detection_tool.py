import os
import sys
import base64
import requests
from typing import Dict, Any, Optional, Tuple, Type
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from pydantic import BaseModel, Field
import json
from PIL import Image
import io


class PestDetectionInput(BaseModel):
    """Input schema for the pest detection tool."""
    image_path: str = Field(description="Path to the image file for pest detection")
    gradio_api_url: str = Field(description="URL of the Gradio API endpoint")


class PestDetectionTool(BaseTool):
    """
    LangChain tool for pest detection that combines a Gradio API endpoint 
    with OpenAI for comprehensive pest analysis and remedy recommendation.
    """
    
    name: str = "pest_detection"
    description: str = """
    Detects pests in images using a machine learning model and provides remedies.
    Takes an image path and Gradio API URL as input.
    """
    args_schema: Type[BaseModel] = PestDetectionInput
    
    # Define the attributes as class fields
    llm: Any = Field(default=None, exclude=True)
    pest_classes: Dict[int, str] = Field(default_factory=dict, exclude=True)
    
    def __init__(self, openai_api_key: str, **kwargs):
        super().__init__(**kwargs)
        
        # Initialize the LLM
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-5-mini", 
        )
        
        # Pest class mapping from the provided classes.txt
        self.pest_classes = {
            1: "rice leaf roller",
            2: "rice leaf caterpillar",
            3: "paddy stem maggot",
            4: "asiatic rice borer",
            5: "yellow rice borer",
            6: "rice gall midge",
            7: "Rice Stemfly",
            8: "brown plant hopper",
            9: "white backed plant hopper",
            10: "small brown plant hopper",
            11: "rice water weevil",
            12: "rice leafhopper",
            13: "grain spreader thrips",
            14: "rice shell pest",
            15: "grub",
            16: "mole cricket",
            17: "wireworm",
            18: "white margined moth",
            19: "black cutworm",
            20: "large cutworm",
            21: "yellow cutworm",
            22: "red spider",
            23: "corn borer",
            24: "army worm",
            25: "aphids",
            26: "Potosiabre vitarsis",
            27: "peach borer",
            28: "english grain aphid",
            29: "green bug",
            30: "bird cherry-oataphid",
            31: "wheat blossom midge",
            32: "penthaleus major",
            33: "longlegged spider mite",
            34: "wheat phloeothrips",
            35: "wheat sawfly",
            36: "cerodonta denticornis",
            37: "beet fly",
            38: "flea beetle",
            39: "cabbage army worm",
            40: "beet army worm",
            41: "Beet spot flies",
            42: "meadow moth",
            43: "beet weevil",
            44: "sericaorient alismots chulsky",
            45: "alfalfa weevil",
            46: "flax budworm",
            47: "alfalfa plant bug",
            48: "tarnished plant bug",
            49: "Locustoidea",
            50: "lytta polita",
            51: "legume blister beetle",
            52: "blister beetle",
            53: "therioaphis maculata Buckton",
            54: "odontothrips loti",
            55: "Thrips",
            56: "alfalfa seed chalcid",
            57: "Pieris canidia",
            58: "Apolygus lucorum",
            59: "Limacodidae",
            60: "Viteus vitifoliae",
            61: "Colomerus vitis",
            62: "Brevipoalpus lewisi McGregor",
            63: "oides decempunctata",
            64: "Polyphagotars onemus latus",
            65: "Pseudococcus comstocki Kuwana",
            66: "parathrene regalis",
            67: "Ampelophaga",
            68: "Lycorma delicatula",
            69: "Xylotrechus",
            70: "Cicadella viridis",
            71: "Miridae",
            72: "Trialeurodes vaporariorum",
            73: "Erythroneura apicalis",
            74: "Papilio xuthus",
            75: "Panonchus citri McGregor",
            76: "Phyllocoptes oleiverus ashmead",
            77: "Icerya purchasi Maskell",
            78: "Unaspis yanonensis",
            79: "Ceroplastes rubens",
            80: "Chrysomphalus aonidum",
            81: "Parlatoria zizyphus Lucus",
            82: "Nipaecoccus vastalor",
            83: "Aleurocanthus spiniferus",
            84: "Tetradacus c Bactrocera minax",
            85: "Dacus dorsalis(Hendel)",
            86: "Bactrocera tsuneonis",
            87: "Prodenia litura",
            88: "Adristyrannus",
            89: "Phyllocnistis citrella Stainton",
            90: "Toxoptera citricidus",
            91: "Toxoptera aurantii",
            92: "Aphis citricola Vander Goot",
            93: "Scirtothrips dorsalis Hood",
            94: "Dasineura sp",
            95: "Lawana imitata Melichar",
            96: "Salurnis marginella Guerr",
            97: "Deporaus marginatus Pascoe",
            98: "Chlumetia transversa",
            99: "Mango flat beak leafhopper",
            100: "Rhytidodera bowrinii white",
            101: "Sternochetus frigidus",
            102: "Cicadellidae"
        }
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Encode image to base64 for API calls."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def call_gradio_api(self, image_path: str, api_url: str) -> Tuple[int, float]:
        """
        Call the Hugging Face Gradio API endpoint for pest classification.
        
        Returns:
            Tuple[int, float]: (predicted_class, confidence_probability)
        """

        api_url = "https://huggingface.co/spaces/subarnoM/EffecientNetPest"
        
        if not os.path.exists(image_path):
            print("❌ Image file not found!")
            return
            
        
        # Method 1: Try Gradio Client
        print(f"\n🔍 Method 1: Gradio Client")
        try:
            from gradio_client import Client, handle_file

            client = Client("subarnoM/EffecientNetPest")
            result = client.predict(
                image=handle_file(image_path),
                api_name="/predict"
            )

            print(f"✅ Gradio Client Success!")
            print(f"📋 Response: {result}")

            # Parse and show results
            if isinstance(result, (list, tuple)) and len(result) >= 1:
                prediction_data = result[0]

                if isinstance(prediction_data, dict) and 'label' in prediction_data:
                    predicted_label = prediction_data['label']
                    confidences_list = prediction_data.get('confidences', [])

                    print(f"\n📊 Results:")
                    print(f"   Predicted: {predicted_label}")

                    # Show top predictions
                    if confidences_list:
                        sorted_confidences = sorted(confidences_list, key=lambda x: x.get('confidence', 0), reverse=True)
                        for i, conf_item in enumerate(sorted_confidences[:3]):
                            label = conf_item.get('label', 'Unknown')
                            conf = conf_item.get('confidence', 0.0)
                            print(f"   {i+1}. {label}: {conf:.4f}")


                    class_num_str = label.replace('Class_', '')
                    predicted_class = int(class_num_str) + 1
                    return predicted_class, conf
                
        except Exception as e:
            print(f"❌ Gradio Client failed: {str(e)}")
            return None, None


    
    def analyze_with_openai_vision(self, image_path: str, pest_name: Optional[str] = None) -> str:
        """
        Analyze image with OpenAI GPT-4 Vision for pest detection and remedy.
        
        Args:
            image_path: Path to the image
            pest_name: If provided, ask for remedy for specific pest
        
        Returns:
            str: Analysis result and remedy recommendation
        """
        try:
            # Encode image
            base64_image = self.encode_image_to_base64(image_path)
            
            if pest_name:
                # High confidence case - ask for remedy for specific pest
                prompt = f"""
                I have detected a pest in this image identified as: {pest_name}
                
                Please provide:
                1. Comprehensive treatment and control measures (Steps)
                2. Prevention strategies
                3. Expected timeline for treatment effectiveness
                
                Please be specific and practical in your recommendations.
                """
            else:
                # Low confidence case - general pest analysis
                prompt = """
                Please analyze this image and determine:
                
                1. Is there a pest visible in this image? (Yes/No)
                2. If yes, what type of pest is it? Please be as specific as possible.
                3. If it's a pest, provide:
                   - Comprehensive treatment and control measures
                   - Prevention strategies
                   - Expected timeline for treatment effectiveness
                4. If it's not a pest, say exactly "THE ENTERED IMAGE IS NOT A PEST, PLEASE ENTER IMAGE OF A PEST".
                
                Please be thorough and practical in your analysis and recommendations.
                """
            
            # Create message with image
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high"
                        }
                    }
                ]
            )
            
            # Get response from OpenAI
            response = self.llm.invoke([message])
            return response.content
            
        except Exception as e:
            return f"Error analyzing image with OpenAI: {str(e)}"
    
    def _run(self, image_path: str, gradio_api_url: str) -> str:
        """
        Main execution method for the tool.
        
        Args:
            image_path: Path to the image file
            gradio_api_url: URL of the Gradio API endpoint
            
        Returns:
            str: Complete analysis and remedy recommendation
        """
        try:
            # Step 1: Call Gradio API for initial classification
            predicted_class, confidence = self.call_gradio_api(image_path, gradio_api_url)
            
            result = f"🔍 **Pest Detection Analysis**\n\n"
            result += f"**Initial ML Model Results:**\n"
            result += f"- Predicted Class: {predicted_class}\n"
            result += f"- Confidence: {confidence:.2%}\n\n"
            
            # Step 2: Decision based on confidence threshold
            if confidence >= 0.75:  # High confidence (≥75%)
                pest_name = self.pest_classes.get(predicted_class, f"Unknown pest (Class {predicted_class})")
                result += f"**High Confidence Detection (≥75%)**\n"
                result += f"Detected Pest: **{pest_name}**\n\n"
                
                # Get specific remedy from OpenAI
                openai_analysis = self.analyze_with_openai_vision(image_path, pest_name)
                result += f"**Expert Analysis & Treatment Recommendations:**\n\n{openai_analysis}"
                
            else:  # Low confidence (<75%)
                result += f"**Low Confidence Detection (<75%)**\n"
                result += f"Performing secondary analysis with AI vision...\n\n"
                
                # Get general analysis from OpenAI
                openai_analysis = self.analyze_with_openai_vision(image_path)
                result += f"**AI Vision Analysis:**\n\n{openai_analysis}"
            
            return result
            
        except Exception as e:
            return f"❌ **Error in pest detection:** {str(e)}\n\nPlease check your image path and API endpoint."
    
    async def _arun(self, image_path: str, gradio_api_url: str) -> str:
        """Async version of the tool (calls sync version)."""
        return self._run(image_path, gradio_api_url)


# Usage example and setup
def create_pest_detection_tool(openai_api_key: str) -> PestDetectionTool:
    """
    Factory function to create the pest detection tool.
    
    Args:
        openai_api_key: Your OpenAI API key
        
    Returns:
        PestDetectionTool: Configured tool instance
    """
    return PestDetectionTool(openai_api_key=openai_api_key)





def test_api_directly():
    """
    Test the API directly with multiple fallback methods when spaces are sleeping/private.
    """
    api_url = "https://huggingface.co/spaces/subarnoM/EffecientNetPest"
    image_path = input("Enter path to test image: ").strip()
    
    if not os.path.exists(image_path):
        print("❌ Image file not found!")
        return
        
    print(f"🔍 Testing API: {api_url}")
    print(f"📸 Using image: {image_path}")
    
    # Method 1: Try Gradio Client
    print(f"\n🔍 Method 1: Gradio Client")
    try:
        from gradio_client import Client, handle_file
        
        client = Client("subarnoM/EffecientNetPest")
        result = client.predict(
            image=handle_file(image_path),
            api_name="/predict"
        )
        
        print(f"✅ Gradio Client Success!")
        print(f"📋 Response: {result}")
        
        # Parse and show results
        if isinstance(result, (list, tuple)) and len(result) >= 1:
            prediction_data = result[0]
            
            if isinstance(prediction_data, dict) and 'label' in prediction_data:
                predicted_label = prediction_data['label']
                confidences_list = prediction_data.get('confidences', [])
                
                print(f"\n📊 Results:")
                print(f"   Predicted: {predicted_label}")
                
                # Show top predictions
                if confidences_list:
                    sorted_confidences = sorted(confidences_list, key=lambda x: x.get('confidence', 0), reverse=True)
                    for i, conf_item in enumerate(sorted_confidences[:3]):
                        label = conf_item.get('label', 'Unknown')
                        conf = conf_item.get('confidence', 0.0)
                        print(f"   {i+1}. {label}: {conf:.4f}")
                        
                return True
                
    except ImportError:
        print("⚠️ gradio_client not installed")
    except Exception as e:
        print(f"❌ Gradio Client failed: {str(e)}")
    
    # Method 2: Check if space is accessible
    print(f"\n🔍 Method 2: Space Status Check")
    try:
        response = requests.get(api_url, timeout=10)
        print(f"Space status: {response.status_code}")
        
        if "Space is sleeping" in response.text:
            print("⚠️ SPACE IS SLEEPING!")
            print("💡 Solution: Visit the space URL to wake it up:")
            print(f"   {api_url}")
            print("   Then wait a few moments and try again.")
            
        elif "private" in response.text.lower():
            print("⚠️ Space appears to be private or restricted")
            
        elif response.status_code == 200:
            print("✅ Space is accessible")
            
    except Exception as e:
        print(f"❌ Cannot reach space: {e}")
    
    # Method 3: Try REST API endpoints
    print(f"\n🔍 Method 3: REST API Endpoints")
    
    base_url = api_url.rstrip('/')
    endpoints = [
        f"{base_url}/api/predict",
        f"{base_url}/run/predict",
        f"{base_url}/call/predict"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"   Testing: {endpoint}")
            
            with open(image_path, 'rb') as f:
                files = {'data': ('image.jpg', f, 'image/jpeg')}
                response = requests.post(endpoint, files=files, timeout=15)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"   ✅ Success! Response: {str(result)[:100]}...")
                    return True
                except:
                    print(f"   ⚠️ Non-JSON response")
            elif response.status_code == 404:
                print(f"   ❌ Endpoint not found")
            elif response.status_code == 503:
                print(f"   ⚠️ Service unavailable (might be sleeping)")
            else:
                print(f"   ❌ Failed: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"   ⏱️ Timeout")
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print(f"\n💡 Troubleshooting Tips:")
    print(f"1. Visit {api_url} to wake up the space if it's sleeping")
    print(f"2. Wait 30-60 seconds for the space to fully load")
    print(f"3. Try uploading an image manually on the web interface first")
    print(f"4. Check if the space is public and functioning")
    
    return False


# Enhanced testing menu
if __name__ == "__main__":

    
    OPENAI_API_KEY = input("Enter OpenAI API key: ").strip()
    GRADIO_API_URL = "https://huggingface.co/spaces/subarnoM/EffecientNetPest"
    IMAGE_PATH = input("Enter image path: ").strip()
    
    if OPENAI_API_KEY and os.path.exists(IMAGE_PATH):
        pest_tool = create_pest_detection_tool(OPENAI_API_KEY)
        result = pest_tool._run(IMAGE_PATH, GRADIO_API_URL)
        print("\n" + "="*60)
        print("PEST DETECTION RESULT:")
        print("="*60)
        print(result)
    else:
        print("❌ Missing API key or invalid image path")
    
