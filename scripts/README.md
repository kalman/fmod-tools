## fmod_parameter_codegen.py

Generates Unity C# code for the parameters of an FMOD Studio project.

You'll be able to write this:

```csharp
public class FootstepPlayer : Component
{
    [SerializeField] private EventReference footstepEvent;

    public void PlayFootstep(float strength, FmodParameters.Surface surface)
    {
        EventInstance footstepEventInstance = RuntimeManager.CreateInstance(footstepEvent);
        footstepEventInstance.setParameterByID(FmodParameters.Strength, strength);
        footstepEventInstance.setSurfaceParameter(surface); // requires the -x parameter
        footstepEventInstance.release();
        footstepEventInstance.start();
    }
}
```

Instead of needing all of this:

```csharp
public class FootstepPlayer : Component
{
    public enum Surface
    {
        Grass,
        Dirt,
        Concrete
    }

    [SerializeField] private EventReference footstepEvent;

    private const string surfaceParameterName = "Surface";
    private const string strengthParaneterName = "Strength";
    private PARAMETER_ID surfaceParameterID;
    private PARAMETER_ID strengthParameterID;

    public void PlayFootstep(Surface surface, float strength)
    {
        EventInstance footstepEventInstance = RuntimeManager.CreateInstance(footstepEvent);
        footstepEventInstance.setParameterByID(strengthParameterID, strength);
        footstepEventInstance.setParameterByID(surfaceParameterID, (float)surface);
        footstepEventInstance.release();
        footstepEventInstance.start();
    }

    private void Start()
    {
        surfaceParameterID = GetParameterID(footstepEvent, surfaceParameterName);
        strengthParameterID = GetParameterID(footstepEvent, strengthParameterID);
    }

    private static PARAMETER_ID GetParameterID(EventReference eventReference, string parameterName)
    {
        EventDescription description = RuntimeManager.GetEventDescription(eventReference);
        description.getParameterDescriptionByName(parameterName, out var paramDescription);
        return paramDescription.id;
    }
}
```

This is:
1. Safer, because you never need to hardcode string parameter names.
1. Efficient, because you never need to make an FMOD API runtime call to resolve GUIDs.
1. Fun, because you don't need to write so much boilerplate.
1. Maintainable, because any change to the FMOD Studio project will automatically go into code.
1. Documenting, because of the docstrings that are generated for the min/max/initial values.

### Basic example

Taking this Footstep example, if your FMOD Studio parameters look like this:

![FMOD Parameters](images/screenshot1.png)

And you run `fmod_parameter_codegen.py` like this:

```commandline
scripts/fmod_parameter_codegen.py Path/To/FMODProject
```

You'll generate this:

```csharp
public static class FmodParameters
{
    public enum SurfaceLabel
    {
        Grass,
        Dirt,
        Concrete,
    }

    /// <summary>
    /// <p>Pitch</p>
    /// Type: float<br/>
    /// Initial: 0<br/>
    /// Min: -12<br/>
    /// Max: 12<br/>
    /// </summary>
    public static readonly PARAMETER_ID Pitch = new() { data1 = 1697321196, data2 = 2101412060 };

    /// <summary>
    /// <p>Surface</p>
    /// Type: SurfaceLabel<br/>
    /// Initial: SurfaceLabel.Grass<br/>
    /// Min: SurfaceLabel.Grass<br/>
    /// Max: SurfaceLabel.Concrete<br/>
    /// </summary>
    public static readonly PARAMETER_ID Surface = new() { data1 = 292778660, data2 = 2674642811 };

    /// <summary>
    /// <p>Strength</p>
    /// Type: float<br/>
    /// Initial: 0<br/>
    /// Min: 0<br/>
    /// Max: 1<br/>
    /// </summary>
    public static readonly PARAMETER_ID Strength = new() { data1 = 3216098345, data2 = 3815392072 };

    public const float PitchMinValue = -12f;
    public const float PitchMaxValue = 12f;
    public const float PitchInitialValue = 0f;

    public const SurfaceLabel SurfaceMinValue = SurfaceLabel.Grass;
    public const SurfaceLabel SurfaceMaxValue = SurfaceLabel.Concrete;
    public const SurfaceLabel SurfaceInitialValue = SurfaceLabel.Grass;

    public const float StrengthMinValue = 0f;
    public const float StrengthMaxValue = 1f;
    public const float StrengthInitialValue = 0f;
}
```

### Advanced options

There are options to generate more advanced code:

```
usage: fmod_parameter_codegen.py [-h] [-o OUTPUT] [-d DIR] [-c CLASSNAME] [-n NAMESPACE] [--debug] [-x EXTENSION] fmod_project

Generate a C# parameter list from an FMOD Studio project.

positional arguments:
  fmod_project          Path to the FMOD Studio project directory

options:
  -h, --help            show this help message and exit
  -o, --output OUTPUT   Output C# file
  -d, --dir DIR         Output C# file is this directory + classname
  -c, --classname CLASSNAME
                        C# class name
  -n, --namespace NAMESPACE
                        Optional C# namespace
  --debug               Generate debug methods
  -x, --extension EXTENSION
                        Generate type-safe enum setter extension methods for classes in form "ClassToExtend.setParameterMethod$set%sFormat" for example: '-x EventInstance.setParameterByID$set%sParameter'
```

For example, if you run this:

```commandline
scripts/fmod_parameter_codegen.py Path/To/FMODProject
```

You'll get:

```csharp
namespace Audio
{
    public static class Params
    {
        public enum SurfaceLabel
        {
            Grass,
            Dirt,
            Concrete,
        }

        /// <summary>
        /// <p>Pitch</p>
        /// Type: float<br/>
        /// Initial: 0<br/>
        /// Min: -12<br/>
        /// Max: 12<br/>
        /// </summary>
        public static readonly PARAMETER_ID Pitch = new() { data1 = 1697321196, data2 = 2101412060 };

        /// <summary>
        /// <p>Surface</p>
        /// Type: SurfaceLabel<br/>
        /// Initial: SurfaceLabel.Grass<br/>
        /// Min: SurfaceLabel.Grass<br/>
        /// Max: SurfaceLabel.Concrete<br/>
        /// </summary>
        public static readonly PARAMETER_ID Surface = new() { data1 = 292778660, data2 = 2674642811 };

        /// <summary>
        /// <p>Strength</p>
        /// Type: float<br/>
        /// Initial: 0<br/>
        /// Min: 0<br/>
        /// Max: 1<br/>
        /// </summary>
        public static readonly PARAMETER_ID Strength = new() { data1 = 3216098345, data2 = 3815392072 };

        public const float PitchMinValue = -12f;
        public const float PitchMaxValue = 12f;
        public const float PitchInitialValue = 0f;

        public const SurfaceLabel SurfaceMinValue = SurfaceLabel.Grass;
        public const SurfaceLabel SurfaceMaxValue = SurfaceLabel.Concrete;
        public const SurfaceLabel SurfaceInitialValue = SurfaceLabel.Grass;

        public const float StrengthMinValue = 0f;
        public const float StrengthMaxValue = 1f;
        public const float StrengthInitialValue = 0f;

#if UNITY_EDITOR
        public static string LookupParameterName(PARAMETER_ID pid)
        {
            if (pid.data1 == 1697321196 && pid.data2 == 2101412060) return "Pitch";
            if (pid.data1 == 292778660 && pid.data2 == 2674642811) return "Surface";
            if (pid.data1 == 3216098345 && pid.data2 == 3815392072) return "Strength";
            return "";
        }
#endif
    }

    public static class EventInstanceParameterExtensions
    {
        public static EventInstance setSurface(this EventInstance self, Params.SurfaceLabel value)
        {
            self.setParameterByID(Params.Surface, (float)value);
            return self;
        }
    }
}
```

### Caveats
- Only works with access to the FMOD Studio project save file (.fspro).
- Only tested with FMOD 2.02 and 2.03.

