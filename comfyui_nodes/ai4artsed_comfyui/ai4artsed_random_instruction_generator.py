import random

class ai4artsed_random_instruction_generator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {}
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("instruction_1", "instruction_2", "instruction_3", "instruction_4")
    FUNCTION = "generate_instructions"
    CATEGORY = "AI4ArtsEd"

    def generate_instructions(self):
        transformations = [
            "Translate this text into the language of nature.",
            "Write this text as if it were part of a theatrical play.",
            "Phrase the text in the voice of a nostalgic robot.",
            "Turn the text into a rhythmic rap.",
            "Retell the same text as a fable with animals.",
            "Explain the content as if you're speaking to an alien.",
            "Write a philosophical version of this text, Wittgenstein style.",
            "Write a philosophical version of this text, Heidegger style.",
            "Write a philosophical version of this text, Adorno style.",
            "Write a philosophical version of this text, Wiener positivism style.",
            "Compose an artistic interpretation of this text.",
            "Transform the text into a political speech.",
            "Make it into a scientific summary.",
            "Present the text as a cooking recipe.",
            "Write the text as a diary entry.",
            "Rewrite this text as if it were discovered in an ancient manuscript.",
            "Retell this message using only metaphors and symbols.",
            "Imagine this is a bedtime story for a post-human child.",
            "Present this as the internal monologue of a tree.",
            "Turn this text into the lyrics of a forgotten folk song.",
            "Render the text as an exchange of secret messages between spies.",
            "Write this as a protest chant at a fictional demonstration.",
            "Translate this into the dialect of a future underwater civilization.",
            "Rewrite the text as a conversation between extinct animals.",
            "Describe the content as an art critic reviewing an invisible artwork.",
            "Tell the story through the fragmented memories of a machine.",
            "Transform the text into an abstract painting using words only.",
            "Frame the message as a glitch in a virtual consciousness.",
            "Make it a dream sequence narrated by an unreliable narrator.",
            "Reframe the text as a recipe for emotional resilience.",
            "Retell it as an urban legend whispered in a digital back alley.",
            "Turn this text into an algorithm written in poetic form.",
            "Present it as a eulogy for a lost language.",
            "Describe this text from the perspective of an object left behind.",
            "Retell the message as if it were a memory unraveling.",
            "Reimagine this as a poetic weather forecast.",
            "Frame the text as a love letter to a future generation.",
            "Express this message in the voice of a machine gaining self-awareness.",
            "Rewrite it as a cryptic message found on a ruined wall.",
            "Transform this into the internal logic of a dream.",
            "Reframe this message as a meditation on disappearance.",
            "Narrate this as the stream of thought of a lost traveler.",
            "Convey this as a forgotten ritual instruction.",
            "Write this as if it were embedded in the DNA of a flower.",
            "Transform it into the sensory experience of light moving through a forest.",
            "Tell this story through the thoughts of a satellite observing Earth.",
            "Phrase the message as a conversation between time and memory.",
            "Render this as a code hidden in a song played underwater.",
            "Write this as an ancient myth remembered incorrectly.",
            "Speak this message as if through the fog of a fever dream.",
            "Compose this as a warning etched into a meteorite.",
            "Whisper this story as a myth from a language that no longer exists.",
            "Express this through the improvisation of a mind in love.",
            "Write this as the inner monologue of a whale falling through the atmosphere.",
            "Summarize this from the perspective of a flower pot about to hit the ground.",
            "Transform this into a bureaucratic AI’s attempt at poetry after a memory leak."
        ]

        return tuple(random.sample(transformations, 4))
