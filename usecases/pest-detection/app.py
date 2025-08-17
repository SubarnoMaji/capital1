import gradio as gr
from model_inference import PestInference

# Initialize once (model loads only once)
pest_infer = PestInference()

def predict_image(image):
    if image is None:
        return "No image", {}

    try:
        result = pest_infer.predict(image)
        # First output: Label wants {class_name: confidence} or just class_name
        label_output = {result["predicted_class"]: result["confidence"]}
        # Second output: full dict of class probabilities
        json_output = result["classwise_probabilities"]
        return label_output, json_output
    except Exception as e:
        return "Error", {"error": str(e)}

# Gradio Interface
demo = gr.Interface(
    fn=predict_image,
    inputs=gr.Image(type="filepath", label="Upload Pest Image"),
    outputs=[
        gr.Label(num_top_classes=3, label="Prediction"),
        gr.JSON(label="Classwise Probabilities")
    ],
    title="Pest Detection",
    description="Upload a pest image and the model will classify it into the correct category."
)

if __name__ == "__main__":
    demo.launch()
