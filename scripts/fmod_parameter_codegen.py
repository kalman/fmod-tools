#!/usr/bin/env python3

import argparse
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path
import struct


EXTENSION_FORMAT = "\"ClassToExtend.setParameterMethod$set%sFormat\""
EXTENSION_FORMAT2 = "\"ClassToExtend.setParameterMethod$set%%sFormat\""


def variable_name(name) -> str:
    chars = []

    if not name[0].isalpha():
        chars.append("_")

    capitalize_next = True
    for c in name:
        if c.isalnum():
            if capitalize_next:
                c = c.capitalize()
                capitalize_next = False
            chars.append(c)
        else:
            capitalize_next = True
    return ''.join(chars)


class Parameter:
    def __init__(self, parameter_id: str, name: str, properties: dict[str, list[str]]):
        self.parameter_id = parameter_id
        self.name = name
        self._properties = properties

    def is_read_only(self) -> bool:
        return self.get_value("isReadOnly", '') == 'true'

    def has_value(self, key: str) -> bool:
        return key in self._properties

    def get_list_value(self, key: str) -> list[str]:
        return self._properties.get(key, [])

    def get_value(self, key: str, default_value: str) -> str:
        values = self.get_list_value(key)
        if len(values) == 0:
            return default_value
        return values[0]

    def is_continuous(self) -> bool:
        return self.get_value("parameterType", '0') == '0'

    def is_discrete(self) -> bool:
        return self.get_value("parameterType", '') == '1'

    def is_labeled(self) -> bool:
        return self.get_value("parameterType", '') == '2'

    def is_user(self) -> bool:
        return self.is_continuous() or self.is_discrete() or self.is_labeled()

    def is_global(self) -> bool:
        return self.get_value("isGlobal", '') == 'true'

    def has_note(self) -> bool:
        return 'note' in self._properties

    def note(self) -> str:
        return self.get_value("note", "")

    def var_name(self) -> str:
        return variable_name(self.name)

    def value_type(self) -> str:
        if self.is_continuous():
            return 'float'
        if self.is_discrete():
            return 'int'
        if self.is_labeled():
            return variable_name(self.name) + "Label"
        raise TypeError()

    def min_value(self, fmt_cpp=False) -> str:
        return self._fmt_value(self.get_value("minimum", '0'), fmt_cpp=fmt_cpp)

    def max_value(self, fmt_cpp=False) -> str:
        mv = self.get_value("maximum", '1')
        if not self.is_continuous():
            # Discrete and labeled parameter maximum values are exclusive in the save file, make them inclusive.
            mv = str(int(mv) - 1)
        return self._fmt_value(mv, fmt_cpp=fmt_cpp)

    def initial_value(self, fmt_cpp=False) -> str:
        return self._fmt_value(self.get_value("initialValue", '0'), fmt_cpp=fmt_cpp)

    def _fmt_value(self, value_str: str, fmt_cpp=False) -> str:
        if self.is_continuous():
            value = float(value_str)
            return f'{value:g}f' if fmt_cpp else f'{value:g}'
        if self.is_discrete():
            value = int(value_str)
            return f'{value}'
        if self.is_labeled():
            idx = int(value_str)
            label = variable_name(self.get_list_value("enumerationLabels")[idx])
            return f'{self.value_type()}.{label}'
        raise TypeError()


class CppPrinter:
    def __init__(self):
        self._lines = []
        self._indent = 0

    def comment(self, line: str):
        self._lines.append(self._indent_str() + "// " + line)

    def line(self, l: str):
        indent = self._indent_str()
        self._lines.append(indent + l)

    def line_no_indent(self, l: str):
        self._lines.append(l)

    def comma_line(self, line: str):
        indent = self._indent_str()
        self._lines.append(indent + line + ",")

    def blank_line(self):
        self._lines.append("")

    def block_start(self, expr: str):
        indent = self._indent_str()
        self._lines.append(indent + expr)
        self._lines.append(indent + "{")
        self._indent += 4

    def block_end(self):
        self._indent = max(self._indent - 4, 0)
        self._lines.append(self._indent_str() + "}")

    def _indent_str(self) -> str:
        return " " * self._indent

    def __str__(self):
        return "\n".join(self._lines)


def build_parameters(project_path: Path) -> list[Parameter]:
    """Returns all Parameters found in the Metadata/ParameterPreset directory of an FMOD project."""

    preset_dir = project_path.parent / "Metadata" / "ParameterPreset"
    presets = []
    properties_by_id = {}

    for xml_path in sorted(preset_dir.glob("*.xml")):
        root = ElementTree.parse(xml_path).getroot()
        for obj in root.findall("object"):
            properties = {
                prop.get("name"): [v.text or "" for v in prop.findall("value")]
                for prop in obj.findall("property")
            }
            properties_by_id[obj.get("id")] = properties

            if obj.get("class") == "ParameterPreset":
                dest = obj.find("relationship[@name='parameter']/destination")
                if dest is not None and dest.text:
                    presets.append((properties["name"][0], obj.get("id"), dest.text.strip()))

    return [Parameter(dest_id, name, {**properties_by_id[preset_id], **properties_by_id[dest_id]}) for name, preset_id, dest_id in presets]


def hashlittle2(data: bytes, initval1: int = 0, initval2: int = 0) -> tuple[int, int]:
    """Bob Jenkins' hashlittle2 (lookup3.c): https://postgis.net/docs/doxygen/3.1/d2/dfa/gserialized2_8c_a28bbffa78951ac929184f31d92a05388.html"""

    mask32 = 0xFFFFFFFF

    def rot(x, k):
        return ((x << k) | (x >> (32 - k))) & mask32

    def mix(a2, b2, c2):
        a2 = (a2 - c2) & mask32
        a2 ^= rot(c2, 4)
        c2 = (c2 + b2) & mask32
        b2 = (b2 - a2) & mask32
        b2 ^= rot(a2, 6)
        a2 = (a2 + c2) & mask32
        c2 = (c2 - b2) & mask32
        c2 ^= rot(b2, 8)
        b2 = (b2 + a2) & mask32
        a2 = (a2 - c2) & mask32
        a2 ^= rot(c2, 16)
        c2 = (c2 + b2) & mask32
        b2 = (b2 - a2) & mask32
        b2 ^= rot(a2, 19)
        a2 = (a2 + c2) & mask32
        c2 = (c2 - b2) & mask32
        c2 ^= rot(b2, 4)
        b2 = (b2 + a2) & mask32
        return a2, b2, c2

    def final(a2, b2, c2):
        c2 ^= b2
        c2 = (c2 - rot(b2, 14)) & mask32
        a2 ^= c2
        a2 = (a2 - rot(c2, 11)) & mask32
        b2 ^= a2
        b2 = (b2 - rot(a2, 25)) & mask32
        c2 ^= b2
        c2 = (c2 - rot(b2, 16)) & mask32
        a2 ^= c2
        a2 = (a2 - rot(c2, 4)) & mask32
        b2 ^= a2
        b2 = (b2 - rot(a2, 14)) & mask32
        c2 ^= b2
        c2 = (c2 - rot(b2, 24)) & mask32
        return a2, b2, c2

    length = len(data)
    a = b = c = (0xdeadbeef + length + initval1) & mask32
    c = (c + initval2) & mask32

    offset, remaining = 0, length
    while remaining > 12:
        k0, k1, k2 = struct.unpack_from("<III", data, offset)
        a = (a + k0) & mask32
        b = (b + k1) & mask32
        c = (c + k2) & mask32
        a, b, c = mix(a, b, c)
        offset += 12
        remaining -= 12

    tail = data[offset:offset + remaining]
    if remaining == 0:
        return c, b
    if remaining == 12:
        k0, k1, k2 = struct.unpack("<III", tail)
        a = (a + k0) & mask32
        b = (b + k1) & mask32
        c = (c + k2) & mask32
    else:
        padded = tail + b"\x00" * (12 - remaining)
        k0, k1, k2 = struct.unpack("<III", padded)
        if remaining > 8:
            a = (a + k0) & mask32
            b = (b + k1) & mask32
            c = (c + (k2 & (mask32 >> (8 * (12 - remaining))))) & mask32
        elif remaining > 4:
            a = (a + k0) & mask32
            b = (b + (k1 & (mask32 >> (8 * (8 - remaining))))) & mask32
        else:
            a = (a + (k0 & (mask32 >> (8 * (4 - remaining))))) & mask32

    a, b, c = final(a, b, c)
    return c, b  # pc, pb


def parameter_id_from_guid(guid: str) -> tuple[int, int]:
    """PARAMETER_ID from a Studio GUID, per FMOD staff:
    https://qa.fmod.com/t/is-there-a-way-to-access-fmod-studio-parameter-id-within-a-studio-script/20577/8
    Each GUID field (Data1, Data2, Data3, Data4) is hashed in turn, with
    the running (data1, data2) threaded through as the seed for the next.
    """
    hex_digits = guid.strip("{}").replace("-", "")
    fields = [
        struct.pack("<I", int(hex_digits[0:8], 16)),  # Data1
        struct.pack("<H", int(hex_digits[8:12], 16)),  # Data2
        struct.pack("<H", int(hex_digits[12:16], 16)),  # Data3
        bytes.fromhex(hex_digits[16:32]),  # Data4
    ]

    data1, data2 = 0, 0
    for field in fields:
        data1, data2 = hashlittle2(field, data1, data2)
    return data1, data2


def generate_csharp(fmod_project: Path, parameters: list[Parameter], classname: str, namespace: str, debug: bool, extensions: str) -> str:
    printer = CppPrinter()

    def escape_argument(argument):
        if " " in argument or "$" in argument:
            return f"'{argument}'"
        return argument

    printer.comment(f"Generated from {fmod_project.name} by {Path(__file__).name} (https://github.com/kalman/fmod-tools) with arguments:")
    printer.comment("    " + " ".join(escape_argument(arg) for arg in sys.argv[1:]))
    printer.blank_line()
    printer.line("using FMOD.Studio;")
    printer.blank_line()

    if namespace:
        printer.block_start("namespace " + namespace)

    printer.block_start("public static class %s" % classname)

    parameters = [p for p in parameters if not p.is_read_only() and p.is_user()]
    labeled_parameters = [p for p in parameters if p.is_labeled()]

    # Generate enums for labelled parameters
    for i, p in enumerate(labeled_parameters):
        if i > 0:
            printer.blank_line()

        printer.block_start("public enum " + p.value_type())
        for label in p.get_list_value("enumerationLabels"):
            printer.comma_line(variable_name(label))
        printer.block_end()

    # Generate PARAMETER_ID for every parameter
    for i, p in enumerate(parameters):
        printer.blank_line()
        printer.line("/// <summary>")
        printer.line(f"/// <p>{p.name}</p>")
        if p.has_note():
            printer.line(f"/// <p>{p.note()}</p>")
        if p.is_global():
            printer.line(f"/// Scope: Global<br/>")
        printer.line(f"/// Type: {p.value_type()}<br/>")
        printer.line(f"/// Initial: {p.initial_value()}<br/>")
        printer.line(f"/// Min: {p.min_value()}<br/>")
        printer.line(f"/// Max: {p.max_value()}<br/>")
        printer.line("/// </summary>")
        (data1, data2) = parameter_id_from_guid(p.parameter_id)
        printer.line(
            "public static readonly PARAMETER_ID %s = new() { data1 = %s, data2 = %s };" % (p.var_name(), data1, data2))

    printer.blank_line()

    for i, p in enumerate(parameters):
        if i > 0:
            printer.blank_line()

        printer.line(f"public const {p.value_type()} {p.var_name()}MinValue = {p.min_value(fmt_cpp=True)};")
        printer.line(f"public const {p.value_type()} {p.var_name()}MaxValue = {p.max_value(fmt_cpp=True)};")
        printer.line(f"public const {p.value_type()} {p.var_name()}InitialValue = {p.initial_value(fmt_cpp=True)};")

    if debug:
        printer.blank_line()
        printer.line_no_indent("#if UNITY_EDITOR");
        printer.block_start("public static string LookupParameterName(PARAMETER_ID pid)")
        for p in parameters:
            (data1, data2) = parameter_id_from_guid(p.parameter_id)
            printer.line(f'if (pid.data1 == {data1} && pid.data2 == {data2}) return "{p.name}";')
        printer.line('return "";')
        printer.block_end()
        printer.line_no_indent("#endif")

    printer.block_end()

    for extension in (extensions or []):
        if not ("." in extension):
            print("error: extension format is " + EXTENSION_FORMAT)
            return ""

        extension_class, extension_method = extension.split(".", 1)

        if not ("$" in extension_method):
            print("error: extension format is " + EXTENSION_FORMAT)
            return ""

        extension_self_method, extension_gen_method_pattern = extension_method.split("$")

        printer.blank_line()
        printer.block_start(f"public static class {extension_class}ParameterExtensions")

        for i, p in enumerate(labeled_parameters):
            if i > 0:
                printer.blank_line()

            enum_type = p.value_type()
            extension_gen_method = extension_gen_method_pattern % p.var_name()
            printer.block_start(f"public static {extension_class} {extension_gen_method}(this {extension_class} self, {classname}.{enum_type} value)")
            printer.line(f"self.{extension_self_method}({classname}.{p.var_name()}, (float)value);")
            printer.line("return self;")
            printer.block_end()

        printer.block_end()

    if namespace:
        printer.block_end()

    printer.blank_line()
    return str(printer)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a C# parameter list from an FMOD Studio project."
    )
    parser.add_argument(
        "fmod_project",
        type=Path,
        help="Path to the FMOD Studio project directory"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output C# file"
    )
    parser.add_argument(
        "-d", "--dir",
        type=Path,
        default=None,
        help="Output C# file is this directory + classname"
    )
    parser.add_argument(
        "-c", "--classname",
        type=str,
        default="FmodParameters",
        help="C# class name"
    )
    parser.add_argument(
        "-n", "--namespace",
        type=str,
        default=None,
        help="Optional C# namespace"
    )
    parser.add_argument(
        "--debug",
        action='store_true',
        help="Generate debug methods"
    )
    parser.add_argument(
        "-x", "--extension",
        type=str,
        action="append",
        help=(f"Generate type-safe enum setter extension methods for classes in form {EXTENSION_FORMAT2} for example: " +
              "'-x EventInstance.setParameterByID$set%%sParameter'")
    )

    args = parser.parse_args()
    fmod_project: Path = args.fmod_project

    if fmod_project.is_dir():
        fspro_files = list(fmod_project.glob("*.fspro"))
        if len(fspro_files) == 0:
            print("error: directory is not an FMOD project, must contain at least one .fspro file")
            return 1
        fmod_project = fspro_files[0]
    elif fmod_project.suffix != ".fspro":
        print("error: file is not an FMOD project, must end with .fspro)")
        return 1

    try:
        parameters = build_parameters(fmod_project)
    except Exception as e:
        print(f"error: failed to parse FMOD project metadata: {e}", file=sys.stderr)
        return 1

    output_text = generate_csharp(fmod_project, parameters, args.classname, args.namespace, args.debug, args.extension)

    if not output_text:
        return 1

    if args.output:
        args.output.write_text(output_text, encoding="utf-8")
    elif args.dir:
        if not args.dir.is_dir:
            print("error: output dir is not a directory")
            return 1
        output_path = args.dir / f"{args.classname}.cs"
        output_path.write_text(output_text, encoding="utf-8")
    else:
        sys.stdout.write(output_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
