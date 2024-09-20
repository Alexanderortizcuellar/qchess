from PIL import Image
from glob import glob
from pathlib import Path


def resize_images(folder_glob: str, ratio: int, output_folder:str):
    images_files = glob(folder_glob)
    images = [Image.open(image) for image in images_files]
    for image, name in zip(images, images_files):
        img = resize_image(image, ratio)
        save(img, name,output_folder)


def resize_image(image: Image, ratio: int):
    new_size = tuple(int(size / ratio) for size in image.size)
    image_resized = image.resize(new_size)
    return image_resized

def save(image: Image, name: str, output_folder: str):
    name = output_folder + "/"  + Path(name).name
    image.save(name, quality=80)

def main():
    resize_images("images/pieces/2048/*.png", 32, "images/pieces/64")


if __name__ == "__main__":
    main()
