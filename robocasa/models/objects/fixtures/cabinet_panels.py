import abc
import xml

from robocasa.models.objects import MujocoXMLObject
from robosuite.utils.mjcf_utils import array_to_string as a2s, find_elements
from robosuite.utils.mjcf_utils import xml_path_completion
from robocasa.models.objects.fixtures.handles import *
from robocasa.utils.object_utils import set_geom_dimensions
from robocasa.models.objects.fixtures.fixture import get_texture_name_from_file

import robocasa


class CabinetPanel(MujocoXMLObject):
    def __init__(
        self,
        xml,
        size, # format: [w, d, h]
        name,
        handle_type="bar",
        handle_config=None,
        handle_hpos=None,
        handle_vpos=None,
        texture=None,
    ):
        super().__init__(
            xml_path_completion(xml, root=robocasa.models.assets_root),
            name=name,
            joints=None,
            duplicate_collision_geoms=True,
        )

        self.size = size
        self.texture = texture

        self.handle_type = handle_type
        self.handle_config = handle_config
        self.handle_hpos = handle_hpos
        self.handle_vpos = handle_vpos
        
        self._set_texture()
        self._create_panel()
        self._add_handle()

    @abc.abstractmethod
    def _get_components(self):
        raise NotImplementedError

    @abc.abstractmethod
    def _create_panel(self):
        pass

    def exclude_from_prefixing(self, inp):
        """
        Exclude all shared materials and their associated names from being prefixed.

        Args:
            inp (ET.Element or str): Element or its attribute to check for prefixing.

        Returns:
            bool: True if we should exclude the associated name(s) with @inp from being prefixed with naming_prefix
        """
        if "tex" in inp:
            return True

        if isinstance(inp, xml.etree.ElementTree.Element):
            if inp.tag == "texture":
                return True

        return False

    def _set_texture(self):
        if self.texture is None:
            return

        self.texture = xml_path_completion(self.texture, root=robocasa.models.assets_root)
        texture = find_elements(
            self.root, tags="texture", 
            attribs={"name": "tex"}, 
            return_first=True
        )
        tex_is_2d = texture.get("type", None) == "2d"
        tex_name = get_texture_name_from_file(self.texture)
        if tex_is_2d:
            tex_name += "_2d"
        texture.set("name", tex_name)
        texture.set("file", self.texture)

        material = find_elements(
            self.root, tags="material", 
            attribs={"name": "{}_mat".format(self.name)},
            return_first=True
        )
        material.set("name", "{}_mat".format(self.name))
        material.set("texture", tex_name)

    def _add_handle(self):
        if self.handle_type is None:
            return
        elif self.handle_type == "bar":
            handle_class = BarHandle
            vpad = 0.20
            hpad = 0.05
        elif self.handle_type == "knob":
            handle_class = KnobHandle
            vpad = 0.05
            hpad = 0.05
        elif self.handle_type == "boxed":
            handle_class = BoxedHandle
            vpad = 0.20
            hpad = 0.05
        else:
            raise NotImplementedError

        panel_w = self.size[0]
        panel_h = self.size[2]
        
        handle = handle_class(
            name="{}_handle".format(self.name),
            panel_w=panel_w,
            panel_h=panel_h,
            **self.handle_config,
        )
        handle_elem = handle.get_obj()
        
        if self.handle_vpos == "bottom":
            handle_z = -(panel_h / 2 - vpad)
        elif self.handle_vpos == "top":
            handle_z = (panel_h / 2 - vpad)
        elif self.handle_vpos == "center":
            handle_z = 0.0
        else:
            raise NotImplementedError

        if self.handle_hpos == "left":
            handle_x = -(panel_w / 2 - hpad)
        elif self.handle_hpos == "right":
            handle_x = (panel_w / 2 - hpad)
        elif self.handle_hpos == "center":
            handle_x = 0.0
        else:
            raise NotImplementedError
        
        handle_elem.set("pos", a2s([handle_x, 0, handle_z]))

        parent_body = self.get_obj()

        self.merge_assets(handle)
        parent_body.append(handle_elem)


class SlabCabinetPanel(CabinetPanel):
    def __init__(self, *args, **kwargs):
        xml = "fixtures/cabinets/cabinet_panels/slab.xml"
        super().__init__(
            xml=xml,
            *args, **kwargs
        )

    def _get_components(self):
        geom_names = ["door"]
        return self._get_elements_by_name(geom_names)[0]

    def _create_panel(self):
        geoms = self._get_components()

        # divide by 2 for mujoco convention
        x, y, z = [dim / 2 for dim in self.size]
    
        sizes = {"door": [x, y, z]}
        positions = {"door": [0, 0, 0]}
        set_geom_dimensions(sizes, positions, geoms, rotated=True)


class ShakerCabinetPanel(CabinetPanel):
    def __init__(
        self, name,
        trim_th=0.02, trim_size=0.08,
        *args, **kwargs
    ):
        self.trim_th = trim_th
        self.trim_size = trim_size

        xml = "fixtures/cabinets/cabinet_panels/shaker.xml"
        super().__init__(
            xml=xml,
            name=name,
            *args, **kwargs
        )

    def _get_components(self):
        geom_names = [
            "door",
            "trim_left", "trim_right", "trim_bottom", "trim_top"
        ]
        return self._get_elements_by_name(geom_names)[0]
    
    def _create_panel(self):
        # divide by 2 for mujoco convention
        x, y, z = self.size
        x, y, z = x / 2, y / 2, z / 2
        trim_th, trim_size = self.trim_th / 2, self.trim_size / 2
        
        # position door and trims such that (0, 0, 0) is center
        door_th = y - trim_th
        door_y = trim_th / 2
        trim_y = -door_th / 2

        sizes = {
            "door": [x - trim_size * 2, door_th, z - trim_size * 2],
            "trim_left": [trim_size, trim_th, z],
            "trim_right": [trim_size, trim_th, z],
            "trim_top": [x - 2 * trim_size, trim_th, trim_size],
            "trim_bottom": [x - 2 * trim_size, trim_th, trim_size]
        }
        positions = {
            "door": [0, door_y, 0],
            "trim_left": [-x + trim_size, trim_y, 0],
            "trim_right": [x - trim_size, trim_y, 0],
            "trim_top": [0, trim_y, z - trim_size],
            "trim_bottom": [0, trim_y, -z + trim_size]
        }

        geoms = self._get_components()
        set_geom_dimensions(sizes, positions, geoms, rotated=True)


class RaisedCabinetPanel(CabinetPanel):
    def __init__(
        self, name,
        trim_th=0.02, trim_size=0.08,
        raised_gap=0.01,
        *args, **kwargs
    ):
        self.trim_th = trim_th
        self.trim_size = trim_size
        self.raised_gap = raised_gap

        xml = "fixtures/cabinets/cabinet_panels/raised.xml"
        super().__init__(
            xml=xml,
            name=name,
            *args, **kwargs
        )

    def _get_components(self):
        geom_names = [
            "door", "door_raised",
            "trim_left", "trim_right", "trim_bottom", "trim_top"
        ]
        return self._get_elements_by_name(geom_names)[0]
    
    def _create_panel(self):
        # place the trims accordingly
        ShakerCabinetPanel._create_panel(self)

        x, y, z = self.size
        x, y, z = x / 2, y / 2, z / 2

        trim_size, trim_th = self.trim_size / 2, self.trim_th / 2
        raised_gap = self.raised_gap / 2

        # place and size the raised portion accordingly, 
        sizes = {"door_raised": [
            x - 2 * trim_size - 2 * raised_gap, 
            trim_th,
            z - 2 * trim_size - 2 * raised_gap
        ]}
        positions = {"door_raised": [0, -(y - trim_th) / 2, 0]}

        geoms = self._get_components()
        set_geom_dimensions(sizes, positions, geoms, rotated=True)


class DividedWindowCabinetPanel(CabinetPanel):
    def __init__(
        self, name,
        trim_th=0.02, trim_size=0.08,
        *args, **kwargs
    ):

        self.trim_th = trim_th
        self.trim_size = trim_size

        xml = "fixtures/cabinets/cabinet_panels/divided_window.xml"
        super().__init__(
            xml=xml,
            name=name,
            *args, **kwargs
        )

    def _get_components(self):
        geom_names = [
            "door",
            "trim_left", "trim_right", "trim_bottom", "trim_top",
            "horiz_trim", "vert_trim"
        ]
        return self._get_elements_by_name(geom_names)[0]
    
    def _create_panel(self):
        # divide by 2 for mujoco convention
        x, y, z = self.size
        x, y, z = x / 2, y / 2, z / 2
        trim_th, trim_size = self.trim_th / 2, self.trim_size / 2
        
        # position door and trims such that (0, 0, 0) is center
        door_th = y - trim_th
        door_y = trim_th / 2
        trim_y = -door_th / 2

        sizes = {
            "door": [x - trim_size * 2, door_th, z - trim_size * 2],
            "trim_left": [trim_size, trim_th, z],
            "trim_right": [trim_size, trim_th, z],
            "trim_top": [x - 2 * trim_size, trim_th, trim_size],
            "trim_bottom": [x - 2 * trim_size, trim_th, trim_size],
            "vert_trim": [trim_size/3.5, trim_th, z],
            "horiz_trim": [x - 2 * trim_size, trim_th, trim_size/3.5]
        }
        positions = {
            "door": [0, door_y, 0],
            "trim_left": [-x + trim_size, trim_y, 0],
            "trim_right": [x - trim_size, trim_y, 0],
            "trim_top": [0, trim_y, z - trim_size],
            "trim_bottom": [0, trim_y, -z + trim_size],
            "vert_trim": [0, trim_y, 0],
            "horiz_trim": [0, trim_y, 0]
        }

        geoms = self._get_components()
        set_geom_dimensions(sizes, positions, geoms, rotated=True)


class FullWindowedCabinetPanel(CabinetPanel):
    def __init__(
        self, name,
        trim_th=0.02, trim_size=0.08,
        opacity=0.5,
        *args, **kwargs
    ):
        self.trim_th = trim_th
        self.trim_size = trim_size
        self.opacity = opacity

        xml = "fixtures/cabinets/cabinet_panels/full_window.xml"
        super().__init__(
            xml=xml,
            name=name,
            *args, **kwargs
        )

    def _get_components(self):
        geom_names = [
            "door",
            "trim_left", "trim_right", "trim_bottom", "trim_top"
        ]
        return self._get_elements_by_name(geom_names)[0]
    
    def _create_panel(self):
        # place the trims accordingly
        ShakerCabinetPanel._create_panel(self)
        self._set_opacity()
    
    def _set_opacity(self):
        transparent_mat = find_elements(
            self.root, tags="material", 
            attribs={"name": f"{self.name}_transparent_material"}, 
            return_first=True
        )
        transparent_mat.set("rgba", f"1 1 1 {self.opacity}")


class CabinetShelf(MujocoXMLObject):
    def __init__(
        self,
        size, # format: [w, d, h]
        texture,
        name,
        pos=None,
    ):
        super().__init__(
            xml_path_completion("fixtures/cabinets/cabinet_panels/shelf.xml", root=robocasa.models.assets_root),
            name=name,
            joints=None,
            duplicate_collision_geoms=True,
        )

        self.size = np.array(size)
        self.pos = pos if pos is not None else [0, 0, 0]
        self._create_panel()

        self.texture = texture
        self._set_texture()

    def exclude_from_prefixing(self, inp):
        """
        Exclude all shared materials and their associated names from being prefixed.

        Args:
            inp (ET.Element or str): Element or its attribute to check for prefixing.

        Returns:
            bool: True if we should exclude the associated name(s) with @inp from being prefixed with naming_prefix
        """        
        if "tex" in inp:
            return True

        if isinstance(inp, xml.etree.ElementTree.Element):
            if inp.tag == "texture":
                return True

        return False
    
    def _set_texture(self):
        if self.texture is None:
            return

        self.texture = xml_path_completion(self.texture, root=robocasa.models.assets_root)
        texture = find_elements(
            self.root, tags="texture", 
            attribs={"name": "tex"}, 
            return_first=True
        )
        tex_is_2d = texture.get("type", None) == "2d"
        tex_name = get_texture_name_from_file(self.texture)
        if tex_is_2d:
            tex_name += "_2d"
        texture.set("name", tex_name)
        texture.set("file", self.texture)

        material = find_elements(
            self.root, tags="material", 
            attribs={"name": "{}_mat".format(self.name)},
            return_first=True
        )
        material.set("texture", tex_name)

    def _get_components(self):
        geom_names = ["shelf"]
        return self._get_elements_by_name(geom_names)[0]

    def _create_panel(self):
        geoms = self._get_components()
        
        sizes = {"shelf": self.size / 2}
        positions = {"shelf": self.pos}
        set_geom_dimensions(sizes, positions, geoms)
