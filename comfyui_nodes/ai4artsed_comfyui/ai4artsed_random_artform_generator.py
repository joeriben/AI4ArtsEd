import random
import time

class ai4artsed_random_artform_generator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # Legacy-Input bleibt bestehen, aber nicht relevant für Zufall
                "random_seed": ("INT",)
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("artform_1", "artform_2", "artform_3", "artform_4")
    FUNCTION = "generate_artforms"
    CATEGORY = "AI4ArtsEd"

    @classmethod
    def ALWAYS_EXECUTE(cls) -> bool:
        # Erzwingt immer neue Ausführung, um Caching zu verhindern
        return True

    def generate_artforms(self, random_seed):
        # Zeitbasierter Seed sorgt für echte Zufälligkeit bei jedem Aufruf
        seed = time.time_ns()
        rng = random.Random(seed)

        artforms = [
            "Rewrite this in the style of Japanese Noh theatre.",
            "Render the text as a Yoruba praise poem.",
            "Transform this into a piece of spoken word poetry.",
            "Write this in the spirit of German Expressionist cinema.",
            "Reframe this message using techniques of Cubism.",
            "Tell this story like an episode of Indian epic theatre.",
            "Compose the text as if it were a fragment of a Maori chant.",
            "Turn this into a surrealist manifesto.",
            "Express this as a scene from a South Korean melodrama.",
            "Adapt this into an Afro-futurist myth.",
            "Tell the story through the rhythm of a Capoeira song.",
            "Render this as instructions from a Bauhaus design manual.",
            "Retell this using traditional Inuit oral storytelling.",
            "Phrase this message like a painting by Frida Kahlo.",
            "Reimagine this as part of a Chinese ink wash painting.",
            "Write this as tango lyrics from Buenos Aires.",
            "Shape the message as a Tibetan prayer wheel invocation.",
            "Turn this into a myth from the Quechua tradition.",
            "Interpret the text in the mood of Scandinavian noir.",
            "Transform this into a Mexican altar offering (ofrenda).",
            "Present this as a scene from a Nigerian Nollywood drama.",
            "Retell this message in the format of a West African griot tale.",
            "Convert this into an Egyptian hieroglyphic inscription.",
            "Express the content through Aboriginal Australian dot painting.",
            "Rephrase this in the tone of a medieval Persian miniature story.",
            "Translate the message into the aesthetics of glitch art.",
            "Present this like a jazz improvisation.",
            "Reframe it as a scene from Italian neorealism.",
            "Adapt this into an avant-garde performance script.",
            "Transform the text into a Haitian Vodou ceremonial chant.",
            "Transform this into a shadow puppet play from Southeast Asia.",
            "Express this like a graffiti mural on a political wall.",
            "Rewrite this in the style of a 90s cyberpunk zine.",
            "Choreograph this message as an Indigenous Australian corroboree dance.",
            "Compose this as a call-and-response chant from the Caribbean.",
            "Render this as a Zapatista resistance broadcast.",
            "Write this like a diary entry from an Amazonian river spirit.",
            "Retell this as a Sámi joik song from northern Europe.",
            "Express this as a coded message within an East German punk zine.",
            "Turn this into an Inuit bone carving narrative.",
            "Translate the text into the brushstrokes of a Tibetan thangka painting.",
            "Reimagine this as an urban legend passed through WhatsApp voice notes.",
            "Frame this as an allegory spoken during a Vodou ceremony in Haiti.",
            "Adapt this into an instructional diagram for a community mural project.",
            "Describe the message through der choreography of a Bharatanatyam solo.",
            "Render this as a riddle spoken in a West African initiation ritual.",
            "Convert this into a sequence of protest posters made in stencil style.",
            "Compose this as a visual poem for a digital screen in public space.",
            "Reframe this message through the movements of a whirling dervish.",
            "Express this in the symbolic logic of a Maori moko tattoo design.",
            "Convert this into the lyrics of a British punk song."
        ]

        # Echte Zufallsauswahl ohne Einfluss durch externe Seeds
        return tuple(rng.sample(artforms, 4))
