import ast
import colorsys
import itertools
import math
import os.path
import re

import numpy as np
import pandas as pd
from PIL import Image, ImageColor, ImageDraw
from skimage.color import rgb2lab
from stl import mesh


class Color:
    DEFAULT_HEX = {
                'C': '#00FFFF',  # Cyan
                'M': "#FF00FF",  # Magenta
                'Y': '#FFFF00',  # Yellow
                'W': '#FFFFFF',  # White
            }
    def __init__(self, name, transmission_distance, hex=None, absorption=None, rgb = None):
        self.name = name
        self.td = transmission_distance
        self.rgb = rgb
        self.absorption = absorption

        if hex == None:
            hex = self.DEFAULT_HEX.get(self.get_label())

        self.update_hex(hex)


    def __repr__(self):
        return self.name

    def update_hex(self, hex):
        self.hex = hex
        self.rgb = ImageColor.getcolor(self.hex, 'RGB')
        self.cmyk = self.get_cmyk()
        self.absorption = self.get_absorption()

    def get_label(self):
        return self.name[0].upper()

    def get_cmyk(self, rgb_scale = 255, cmyk_scale = 1):
        r, g, b = self.rgb
        if (r, g, b) == (0, 0, 0):
            # black
            return 0, 0, 0

        # rgb [0,255] -> cmy [0,1]
        c = 1 - r / rgb_scale
        m = 1 - g / rgb_scale
        y = 1 - b / rgb_scale

        # extract out k [0, 1]
        min_cmy = min(c, m, y)
        c = (c - min_cmy) / (1 - min_cmy)
        m = (m - min_cmy) / (1 - min_cmy)
        y = (y - min_cmy) / (1 - min_cmy)
        k = min_cmy

        return c * cmyk_scale, m * cmyk_scale, y * cmyk_scale, k * cmyk_scale

    def get_absorption(self):
        rate = (255 - np.array(self.rgb)) / 255
        return rate

    @staticmethod
    def get_transmission_rate(d, td, alpha=12):
        # Beer–Lambert law
        x = alpha * d  / td
        T = np.exp(- x) # transmission rate
        return T

    @staticmethod
    def get_lab(rgb):
        rgb_normalized = np.array(rgb) / 255.0  # Convert [0,255] to [0,1]
        lab = rgb2lab(np.array([rgb_normalized]))  # rgb2lab expects shape (1, 3) or (H, W, 3)
        L, a, b = lab[:,0], lab[:,1], lab[:,2]
        C = np.sqrt(a**2 + b**2)
        return L, a, b, C

    @staticmethod
    def is_neutral(rgb, threshold = 10):
        L, a, b, C = Color.get_lab(rgb)
        return C < threshold or np.std(rgb) < threshold

    @staticmethod
    def is_brown(rgb):
        L, a, b, C = Color.get_lab(rgb)
        return Color.is_neutral(rgb) and L < 60 and a > 5 and b > 10

    @staticmethod
    def map_to_nearest_color(input_colors, reference_code, reference_rgb):
        """
        For each input RGB tuple, find the closest RGB tuple in a reference matrix.
        Distance is computed in LAB color space (perceptual).

        Parameters:
            input_colors (list of tuples): e.g. [(R,G,B), ...]
            reference_matrix (list of lists): 2D matrix [[(R,G,B),...], [...]]
                                            OR cells may be (code, rgb_tuple)

        Returns:
            result list of blend code for each color
        """

        # ----------- Extract pure RGB tuples from reference matrix ------------
        ref_colors = []
        ref_blend_codes = []
        coords = []   # store (row,col) mapping

        for r_idx in range(reference_code.shape[0]):
            for c_idx in range(reference_code.shape[1]):
                code = reference_code.iat[r_idx, c_idx]
                rgb = reference_rgb.iat[r_idx, c_idx]
                ref_colors.append(rgb)
                ref_blend_codes.append(code)
                coords.append((r_idx, c_idx))


        ref_colors = np.array(ref_colors) / 255.0
        ref_lab = rgb2lab(ref_colors.reshape(-1, 1, 3)).reshape(-1, 3)

        # ----------- Convert input to LAB ------------
        inp = np.array(input_colors) / 255.0
        inp_lab = rgb2lab(inp.reshape(-1, 1, 3)).reshape(-1, 3)

        results_code = []
        results_color = []

        # ----------- For each input color, find nearest reference color --------
        for lab_color in inp_lab:
            # Compute Euclidean distance in LAB
            dists = np.linalg.norm(ref_lab - lab_color, axis=1)
            nearest_idx = np.argmin(dists)
            results_code.append(ref_blend_codes[nearest_idx])
            results_color.append(ref_colors[nearest_idx]*255)

        return results_code, results_color

class Colors:
    DEFAULT_TD = {'C': 3, 'M': 1.9, 'Y': 2.5, 'W': 7.2}
    BAMBU_CMYK_HEX = {
                        'C': "#0086D6",  # Cyan
                        'M': "#EC008C",  # Magenta
                        'Y': '#F4EE2A',  # Yellow
                        'W': '#FFFFFF',  # White
            }

    DEFAULT_CLEAR_TD = {'C': 60, 'M': 100, 'Y': 70, 'W': 200}
    CLEAR_CMYK_HEX = {
                        'C': "#0089cd",  # Cyan
                        'M': "#e75d4a",  # Magenta
                        'Y': '#f6d449',  # Yellow
                        'W': '#FFFFFF',  # White
            }
    PRIMARY_COLORS = ['C', 'M', 'Y', 'W']

    def __init__(self, colors=None, clear=False, names = None):
        self.colors = colors if colors is not None else {}
        self.white_balance = {
            'r': 0,
            'g': 10,
            'b': 24
        }

        if names is not None:
            for c in names:
                if clear:
                    hex = self.BAMBU_CMYK_HEX.get(c, '#FFFFFF')
                    self.colors[c] = Color(c, Colors.DEFAULT_CLEAR_TD.get(c), hex)

                else:
                    hex = self.CLEAR_CMYK_HEX.get(c, '#FFFFFF')
                    self.colors[c] = Color(c, Colors.DEFAULT_TD.get(c), hex)
        else:
            # init with cmyw
            for c in Colors.PRIMARY_COLORS:
                if clear:
                    hex = self.CLEAR_CMYK_HEX.get(c, '#FFFFFF')
                    self.colors[c] = Color(c, Colors.DEFAULT_CLEAR_TD.get(c), hex)

                else:
                    hex = self.BAMBU_CMYK_HEX.get(c, '#FFFFFF')
                    self.colors[c] = Color(c, Colors.DEFAULT_TD.get(c), hex)


    def __len__(self):
        return len(self.colors)

    def __getitem__(self, label):
        label = label.strip().upper()
        return self.colors[label]

    def __setitem__(self, label, value=None):
        label = label.strip().upper()
        self.colors[label.strip().upper()] = value

    def add(self, color):
        self.colors[color.get_label()] = color

    def update_white_balance(self, new_r, new_b, new_g):
        self.white_balance['r'] = new_r
        self.white_balance['b'] = new_b
        self.white_balance['g'] = new_g

    def get_labels(self):
        return [x for x in self.colors]

class BlendTestGenerator:
    def __init__(self, plate_length=13*16, plate_width=13*16, grid_length=13, grid_width=13, layer_height=.08, layer_count_max=4,
                 same_height=False, rearrange_by_size = True, sort_color=True, verbose = True,
                 directory = 'output',
                 colors = Colors()
                ):
        self.length_total = plate_length
        self.width_total = plate_width
        self.grid_length = grid_length
        self.grid_width = grid_width
        self.layer_height = layer_height
        self.layer_count_max = layer_count_max
        self.colors = colors
        self.reshape = rearrange_by_size
        self.same_height = same_height
        self.sort_color = sort_color
        self.verbose = verbose
        self.filename = f'{''.join(self.colors.get_labels())}_{self.length_total}x{self.width_total}x{self.layer_height * self.layer_count_max:.2f}'
        self.directory = f'./{directory}/{self.filename}/'
        self.df_code = pd.DataFrame()
        self.df_rgb = pd.DataFrame()

    def reshape_matrix(self, df):
        # split
        split_num_x = df.shape[0] * df.shape[1] * self.grid_length // self.length_total
        split_num_y = df.shape[0] * df.shape[1] // split_num_x

        if split_num_x > 0 and self.reshape:
            df = pd.DataFrame(np.reshape(df, (split_num_y, split_num_x)))
        else:
            df = df

        if self.verbose:
            print(f"Length per cell: {self.grid_length:.2f}, Width per cell: {self.grid_width}, Layer height: {self.layer_height}")
            print(f'Total build volume: Length={self.length_total}, Width={self.width_total}, Height={self.layer_height * self.layer_count_max}')

        return df, self.grid_length, self.grid_width

    def merge_meshes_by_color(self, meshes):
        for color in meshes:
            filename = f'{''.join(self.colors.get_labels())}_{color}_{self.length_total}x{self.width_total}x{self.layer_height * self.layer_count_max:.2f}.stl'
            self.save_stl_mesh(self.merge_stl_meshes(meshes[color]), filename)

    def generate(self):
        if self.same_height:
            df = self.permutation_matrix(self.colors.get_labels(), self.layer_count_max)
        else:
            df = self.combined_permutation_matrix(self.colors.get_labels(), self.layer_count_max)


        # reshape based on plate dimension
        df, grid_length, grid_width = self.reshape_matrix(df)

        # generate rgb based on code
        df_rgb, df_code = self.set_code_rgb_df(df)

        meshes = {color: []  for color in self.colors.get_labels()}
        for y in range(df_code.shape[0]):
            for x in range(df_code.shape[1]):
                if not pd.isna(df_code.iat[y, x]):
                    code = df_code.iat[y, x]
                    for color_idx in range(len(code)):
                        color = code[color_idx]
                        x_range = [grid_length*(x), grid_length*(x+1)]
                        y_range = [grid_width*y, grid_width*(y+1)]
                        z_range = [self.layer_height * color_idx, self.layer_height * (color_idx + 1)]
                        # if self.verbose:
                        #     print(f"{len(code)} layers: [{code}:{code[color_idx]}]. "
                        #         f"x=[{x_range}], "
                        #         f"y=[{y_range}], "
                        #         f"z=[{z_range}]")
                        meshes[color].append(self.generate_box(x_range, y_range, z_range))

        self.merge_meshes_by_color(meshes)
        self.save_matrix_csv()
        self.save_matrix_image()

        return df_rgb, df_code

    def combined_permutation_matrix(self, items, count):
        """
        Generate a combined permutation matrix for the given items and count.
        """
        matrix = []
        for first in items:
            row = [first]
            for length in range(2, count + 1):
                combos = [first + ''.join(p) for p in itertools.product(items, repeat=length - 1)]
                row.extend(combos)
            # row.sort()
            matrix.append(row)
        max_len = max(len(r) for r in matrix)

        for r in matrix:
            while len(r) < max_len:
                r.append('[]')

        cols = [l for l in range(max_len)]
        rows = [r for r in range(len(items))]
        df = pd.DataFrame(matrix, index=rows, columns=cols)
        return df

    def permutation_matrix(self, items, count):
        """
        Generate a permutation matrix for the given items and count.
        """
        perms = list(itertools.product(items, repeat=count))
        joined  = [''.join(p) for p in perms]
        row = len(items)
        col = len(joined) // row
        matrix = [joined[i*col:(i+1)*col] for i in range(row)]

        df = pd.DataFrame(matrix)
        return df

    def generate_box(self, xrange, yrange, zrange):
        """
        Create a 3D box mesh from the given coordinate ranges.
        """
        x1, x2 = xrange
        y1, y2 = yrange
        z1, z2 = zrange

        vertices = np.array([
            [x1, y1, z1],
            [x2, y1, z1],
            [x2, y2, z1],
            [x1, y2, z1],
            [x1, y1, z2],
            [x2, y1, z2],
            [x2, y2, z2],
            [x1, y2, z2]
        ])

        faces = np.array([
            [0,3,1], [1,3,2],    # bottom
            [0,4,7], [0,7,3],    # left
            [4,5,6], [4,6,7],    # top
            [5,1,2], [5,2,6],    # right
            [2,3,6], [3,7,6],    # back
            [0,1,5], [0,5,4]     # front
        ])

        box = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
        for i, f in enumerate(faces):
            for j in range(3):
                box.vectors[i][j] = vertices[f[j], :]

        return box

    def merge_stl_meshes(self, mesh_list):
        """
        Merge multiple STL mesh objects into a single mesh.
        """
        # Calculate the total number of faces
        total_faces = sum(m.data.shape[0] for m in mesh_list)
        # Create a new Mesh to store all faces
        combined = mesh.Mesh(np.zeros(total_faces, dtype=mesh.Mesh.dtype))

        current_index = 0
        for m in mesh_list:
            n = m.data.shape[0]
            combined.data[current_index:current_index + n] = m.data
            current_index += n

        return combined


    def save_stl_mesh(self, mesh_obj, filename):
        """
        Save the given STL mesh object to a stl file.
        """

        file_path = os.path.join(self.directory, filename)
        if not os.path.isdir(self.directory):
            os.mkdir(self.directory)
        mesh_obj.save(file_path)
        return mesh_obj

    def save_matrix_csv(self):
        """
        Save the given DataFrame to a CSV file.
        """

        file_path = os.path.join(self.directory, self.filename)
        if not os.path.isdir(self.directory):
            os.mkdir(self.directory)
        self.df_rgb.to_csv(file_path+'_rgb.csv', index=False)
        self.df_code.to_csv(file_path+'_code.csv', index=False)

    def read_matrix_csv(self, filename):
        # read CSV forcing strings
        df_raw = pd.read_csv(model.directory+filename,
                            header=0, dtype=str)

        df_parsed = df_raw.map(self.parse_cell)

        # # If you want separate label and rgb matrices:
        # df_label = df_parsed.applymap(lambda v: v[0] if isinstance(v, tuple) else v)
        # df_rgb   = df_parsed.applymap(lambda v: tuple(map(float, v[1])) if isinstance(v, tuple) else v)

        # Example access
        # print(df_label.iloc[0,0])   # 'WWWW'
        # print(df_rgb.iloc[0,0])     # (255.0, 255.0, 255.0)
        return df_parsed

    def matrix_to_code_color_map(self, df_rgb, df_code):
        map = {}
        n_rows, n_cols = df_rgb.shape

        for r in range(n_rows):
            for c in range(n_cols):
                code = df_code.iloc[r, c]
                rgb = df_rgb.iloc[r, c]
                map[code] = rgb
        return map

    def set_code_rgb_df(self, df):
        """
        """
        records = []
        n_rows, n_cols = df.shape

        # Sort first by hue (left to right), then by lightness (top to bottom)
        df_rgb = pd.DataFrame(records)

        for r in range(n_rows):
            for c in range(n_cols):
                code = df.iloc[r, c]
                rgb = self.code_to_rgb(code)
                h, l, s = colorsys.rgb_to_hls(*rgb)
                tone = 2
                if Color.is_neutral(rgb, 15.5):
                    tone = 0
                if Color.is_brown(rgb):
                    tone = 1
                records.append({
                    "old_row": r,
                    "old_col": c,
                    "rgb": rgb,
                    'code': code,
                    "hue": h,
                    "light": l,
                    "saturation": s,
                    "tone": tone
                })

        # Sort first by hue (left to right), then by lightness (top to bottom)
        df_rgb = pd.DataFrame(records)
        df_code = pd.DataFrame()
        sorted_by_hue = df_rgb.sort_values(by=["tone", "hue"], ascending=[False, True]).reset_index(drop=True)
        df_rgb = pd.DataFrame(index=range(n_rows), columns=range(n_cols), dtype=object)
        cols_per_hue = np.array_split(sorted_by_hue, n_cols)
        for new_c, col_group in enumerate(cols_per_hue):
            # sort by light
            col_sorted = col_group.sort_values(by=["tone", "light", "code"], ascending=[False, False, True]).reset_index(drop=True)
            # fill
            for new_r in range(min(n_rows, len(col_sorted))):
                if self.sort_color:
                    df_rgb.iloc[new_r, new_c] =  col_sorted.loc[new_r]['rgb']
                    df_code.loc[new_r, new_c] =  col_sorted.loc[new_r]['code']
                else:
                    df_rgb.iloc[col_sorted.loc[new_r]['old_row'], col_sorted.loc[new_r]['old_col']] =  col_sorted.loc[new_r]['rgb']
                    df_code.loc[col_sorted.loc[new_r]['old_row'], col_sorted.loc[new_r]['old_col']] =  col_sorted.loc[new_r]['code']
        self.df_code = df_code
        self.df_rgb = df_rgb
        return df_rgb, df_code


    def code_to_rgb(self, code: str):
        """
        Layered optical mixing using Beer–Lambert
        td: bound to material, not floating
        """
        if not code:
            return (255, 255, 255)

        code = code.strip().upper()
        tranmission = [Color.get_transmission_rate(self.layer_height, self.colors[c].td, alpha=23) for c in code]

        remain = 1
        light_loss_ratio = np.zeros(self.layer_count_max+1)

        for i, t in enumerate(tranmission):  # top to bottom
            light_loss_ratio[i] = remain * (1-t)
            remain *= t
        light_loss_ratio[i+1] = remain * (1-t)

        # Normalize
        light_loss_ratio = light_loss_ratio / np.sum(light_loss_ratio)

        rgb = np.ones(3)
        for i, c in enumerate(code):
            color = self.colors[c]
            rgb -= color.get_absorption() * light_loss_ratio[i] # accumulate light loss
        # simulate white background if additional light passes all layers
        rgb = light_loss_ratio[-1] * np.ones(3) + (1 - light_loss_ratio[-1]) * rgb
        return tuple(rgb * 255)


    def save_matrix_image(self, save_blank = True):
        rows, cols = self.df_code.shape
        cell_size = 50  # pixels per cell
        rgb_array = np.zeros((rows*cell_size, cols*cell_size, 3), dtype=np.uint8)
        for y in range(rows):
            for x in range(cols):
                rgb = self.df_rgb.iat[y, x]
                if rgb == None:
                    rgb_array[y*cell_size:(y+1)*cell_size, x*cell_size:(x+1)*cell_size] = (255, 255, 255)
                else:
                    rgb_array[y*cell_size:(y+1)*cell_size, x*cell_size:(x+1)*cell_size] = rgb

        file_path = os.path.join(self.directory, self.filename+'.png')
        if not os.path.isdir(self.directory):
            os.mkdir(self.directory)
        img = Image.fromarray(rgb_array)
        draw = ImageDraw.Draw(img)
        img_blank = Image.fromarray(rgb_array)
        draw_blank = ImageDraw.Draw(img_blank)
        for y in range(rows):
            for x in range(cols):
                if (self.df_code.iat[y, x] == None):
                    continue
                else:
                    if pd.isna(self.df_code.iat[y, x]):
                        continue
                    code = self.df_code.iat[y, x]
                    rgb = tuple(rgb_array[y*cell_size, x*cell_size])
                    rgb_blank = (255, 255, 255)
                    x0, y0 = x*cell_size, y*cell_size
                    x1, y1 = x0+cell_size, y0+cell_size
                    draw.rectangle([x0, y0, x1, y1], fill=rgb)
                    draw_blank.rectangle([x0, y0, x1, y1], fill=rgb_blank, outline=(0, 0, 0))
                    # Decide text color based on cell brightness
                    brightness = (rgb[0]*0.299 + rgb[1]*0.587 + rgb[2]*0.114)/255
                    text_color = (0,0,0) if brightness > 0.5 else (255,255,255)
                    draw.text((x0, y0), code, fill=text_color)
                    draw_blank.text((x0, y0), code, fill=(0, 0, 0))
        img.save(file_path)
        if save_blank:
            img_blank.save(f'{file_path[:-4]}_blank.png')


    def image_to_rgb_matrix(self, image_path, grid_size=16, sample_fraction=0.4, method='mean', save_samples=False):
        """
        rectangle of grid for calibration
        """
        img = Image.open(image_path).convert('RGB')
        w, h = img.size
        cell_w, cell_h = w / grid_size, h / grid_size
        arr = np.array(img)

        rgb_matrix = []
        for row in range(grid_size):
            row_colors = []
            for col in range(grid_size):
                # edge
                x0 = int(col * cell_w)
                x1 = int((col + 1) * cell_w)
                y0 = int(row * cell_h)
                y1 = int((row + 1) * cell_h)

                # shrink grid
                margin_x = int((1 - sample_fraction) * (x1 - x0) / 2)
                margin_y = int((1 - sample_fraction) * (y1 - y0) / 2)
                xs, xe = x0 + margin_x, x1 - margin_x
                ys, ye = y0 + margin_y, y1 - margin_y

                # sample
                patch = arr[ys:ye, xs:xe, :]
                if method == 'median':
                    color = tuple(np.median(patch.reshape(-1, 3), axis=0).astype(int))
                else:
                    color = tuple(np.mean(patch.reshape(-1, 3), axis=0).astype(int))
                row_colors.append(color)

                if save_samples:
                    filename = f"tile{row}_{col}.png"
                    directory = self.directory+'samples/'
                    file_path = os.path.join(directory, filename)
                    if not os.path.isdir(directory):
                        os.mkdir(directory)

                    # save and check cropped sample
                    cell = img.crop((xs, ys, xe, ye))
                    # Save cropped image
                    cell.save(file_path)
            rgb_matrix.append(row_colors)

        df = pd.DataFrame(rgb_matrix)
        return df

    def color_variance(self, df_ref, df_photo, new_df_rgb, new_df_code, save_comp_img = False):
        rows, cols = df_ref.shape
        if df_ref.shape != df_photo.shape:
            return

        code_color_map = self.matrix_to_code_color_map(new_df_rgb, new_df_code)

        diffs = np.zeros((rows, cols))
        max_diff = math.sqrt(255 ** 2 *3)

        for y_idx in range(df_ref.shape[0]):
            for x_idx in range(df_ref.shape[1]):
                photo_code = df_ref.iat[y_idx, x_idx][0]
                photo_rgb = df_photo.iat[y_idx, x_idx]
                new_rgb = code_color_map[photo_code]

                # df_photo.iloc[y_idx, x_idx] =  tuple((photo_code, photo_rgb))
                diff = math.sqrt((new_rgb[0]-photo_rgb[0]) ** 2 + (new_rgb[1]-photo_rgb[1]) ** 2 + (new_rgb[2]-photo_rgb[2]) ** 2) / max_diff
                diffs[y_idx, x_idx] = round(diff, 2)
                # if self.verbose:
                #     print(f'code: {df_gen.iat[y_idx, x_idx][0]}, preview:{gen_rgb}, photo_sample:{photo_rgb}')
        # if save_comp_img:
        #     self.save_matrix_image(df_photo, df_rgb, 'sample.png', False)

        avg = np.average(pd.DataFrame(diffs))
        wrong_color_count = dict.fromkeys(self.colors.get_labels(), 0)
        for y_idx in range(df_ref.shape[0]):
            for x_idx in range(df_ref.shape[1]):
                if diffs[y_idx, x_idx] > avg:
                    code, _ = df_ref.iloc[y_idx][x_idx]
                    for c in code:
                        wrong_color_count[c] = wrong_color_count[c] + diffs[y_idx, x_idx]
        print(wrong_color_count)
        return avg


    def parse_cell(self,s):
        if pd.isna(s):
            return s
        if not isinstance(s, str):
            return s
        # remove np.float64(...) wrappers
        s2 = re.sub(r'np\.float64\(([^)]+)\)', r'\1', s)
        try:
            return ast.literal_eval(s2)   # yields ('CODE', (r, g, b))
        except Exception:
            return s2

if __name__ == "__main__":
    p1s_plate = 256, 228, 256
    a1_plate = 256, 256, 256
    four = BlendTestGenerator(
        colors=Colors(clear=False),
        same_height=True, sort_color=True, verbose=True,
        layer_height=0.08, layer_count_max=4)

    clear = BlendTestGenerator(
        colors=Colors(clear=True),
        layer_height=.28*3, layer_count_max=4,
        same_height=True, sort_color=True, verbose=False
        )


    model = four
    df_rgb, df_code = model.generate()

    # df_ref = model.read_matrix_csv('IMG_6785.csv')
    # # df_ref_clear = model.read_matrix_csv('IMG_6803.csv')

    # df_photo = model.image_to_rgb_matrix(model.directory+'IMG_6785.JPG', save_samples=True)
    # print(model.color_variance(df_ref, df_photo, df_rgb, df_code, save_comp_img=True))

    print(Color.map_to_nearest_color([(0, 0, 0)], df_code, df_rgb))
