from PyQt5.QtCore import QObject


class Rules(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    def check_move(self, src, dst):
        pass

    def check_castle(self, src, dst):
        mappings = {
            "e1": [["g1", "f1"], ["c1", "d1"]],
            "e8": [["g8", "f8"], ["c8", "d8"]],
        }
        if src.objectName() in mappings.keys():
            if src.piece.name == "K" or src.piece.name == "k":
                for move in mappings[src.objectName()]:
                    if move[0] == dst.objectName():
                        return True
                return False

        return False

    def check_en_passant(self, src, dst):
        mappings = {
            "a5": [["b6", "b5"]],
            "b5": [["a6", "a5"], ["c6", "c5"]],
            "c5": [["b6", "b5"], ["d6", "d5"]],
            "d5": [["c6", "c5"], ["e6", "e5"]],
            "e5": [["d6", "d5"], ["f6", "f5"]],
            "f5": [["e6", "e5"], ["g6", "g5"]],
            "g5": [["f6", "f5"], ["h6", "h5"]],
            "h5": [["g6", "g5"]],
        }
        white_mappings = {}
        for key, value in mappings.items():
            key = key.replace("5", "4")
            white_mappings[key] = []
            for move in value:
                white_mappings[key].append(
                    [move[0].replace("6", "3"), move[1].replace("5", "4")]
                )


        if src.objectName() in mappings.keys() and src.piece.name.lower() == "p":
            for move in mappings[src.objectName()]:
                if move[0] == dst.objectName():
                    return True

        if src.objectName() in white_mappings.keys() and src.piece.name.lower() == "p":
            for move in white_mappings[src.objectName()]:
                if move[0] == dst.objectName():
                    return True

        return False

    def check_promotion(self, src, dst):
        if src.piece.name.lower() == "p" and (dst.objectName()[-1] == "8" or dst.objectName()[-1] == "1"):
            return True
        return False
