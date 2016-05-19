@0xccbfcab600d976ab;

using ID = UInt32;

using DIM = Int32;


# Basic Mathematical types
struct Point2 {
	x @0 :DIM;
	y @1 :DIM;
}

struct Point2f {
	x @0 :Float64;
	y @1 :Float64;
}

# Terms stored row-major order
struct Matrix3x3 {
	t0 @0 :Float64;
	t1 @1 :Float64;
	t2 @2 :Float64;
	t3 @3 :Float64;
	t4 @4 :Float64;
	t5 @5 :Float64;
	t6 @6 :Float64;
	t7 @7 :Float64;
	t8 @8 :Float64;
}

struct Matrix4x4 {
	t0 @0 :Float64;
	t1 @1 :Float64;
	t2 @2 :Float64;
	t3 @3 :Float64;
	t4 @4 :Float64;
	t5 @5 :Float64;
	t6 @6 :Float64;
	t7 @7 :Float64;
	t8 @8 :Float64;
	t9 @9 :Float64;
	t10 @10 :Float64;
	t11 @11 :Float64;
	t12 @12 :Float64;
	t13 @13 :Float64;
	t14 @14 :Float64;
	t15 @15 :Float64;
}


enum Units {
	mm @0;
	inches @1;
}

struct DimensionUnits {
	scalar @0 :DIM;
	units @1 :Units; 
}

struct Handle {
	union {
		none  @0 :Void;
		point @1 :Point2f;
	}
}

struct OptionalDim {
	union {
		none @0 :Void;
		dim  @1 :DIM;
	}
}

struct ImageTransform {
	matrix @0 :Matrix3x3;

	struct KeypointTransformMeta {
		struct KeyPointLocation {
			# SID of the keypoint the location is for
			kpSid @0 :ID;

			# Location on the layer. Use floating-point rep since we want subpixel accuracy
			position @1 :Point2f;
		}

		# List of keypoint locations on layers
		keypoints @0 :List(KeyPointLocation);
	}
	
	struct RectTransformMeta {
		enum OriginCorner {
			lowerLeft @0;
			lowerRight @1;
			upperLeft @2;
			upperRight @3;
		}

		handles @0 :List(Handle);
		dimHandles @1 :List(Handle);
		lockedToDim @2 :Bool;
		originCenter @3 :Point2f;
		originCorner @4 :OriginCorner;
		dims @5 :List(Float32);
		flipX @6 :Bool;
		flipY @7 :Bool;

	}

	meta :union {
		noMeta @1 :Void;
		rectTransformMeta @2 :RectTransformMeta;
		keypointTransformMeta @3 :KeypointTransformMeta;
	}

}


struct Keypoint {
	sid @0 :ID;
	worldPosition @1 :Point2;
}

struct Image {
	sid @0 :ID;
	name @1 :Text;
	data @2 :Data;
	transform @3 :ImageTransform;
}

struct Net {
	sid @0 :ID;
	name @1 :Text;
	nclass @2 :Text;
}


struct Imagery {
	imagelayers @0 :List(Image);
	keypoints @1 :List(Keypoint);
}

struct Polygon {
	exterior @0 :List(Point2);
	interiors @1 :List(List(Point2));

	layerSid @2 :ID;
	netSid @3 :ID;

}

struct Via {
	point @0 :Point2;
	r @1 :DIM;
	viapairSid @2 :ID;
	netSid @3 :ID;
}

struct Trace {
	p0 @0 :Point2;
	p1 @1 :Point2;
	thickness @2 :DIM;
	netSid @3 :ID;
	layerSid @4  :ID;
}

struct Artwork {
	vias @0 :List(Via);
	traces @1 :List(Trace);
	polygons @3 :List(Polygon);
	airwires @4 :List(Airwire);

	components @2  :List(Component);
}

struct Airwire {
	p0 @0 :Point2;
	p1 @1 :Point2;
	p0LayerSid @2 :ID;
	p1LayerSid @3 :ID;
	netSid @4 :ID;

}


struct Color3f {
	r @0 :Float32;
	g @1 :Float32;
	b @2 :Float32;
}

# Components

enum PinClass {
}

struct PinInfo {
	identifier @0 :Text;
	name @1 :Text;
	class @2 :PinClass;
	net @3 :ID;
}

enum Side {
	top @0;
	bottom @1;
}

struct CmpGeneral {
	sid @0 :ID;
	refdes @1 :Text;

	center @2 :Point2;
	theta @3 :Float32;
	side @4 :Side;

	pininfo @5 :List(PinInfo);

	partno @6 :Text;
}

struct DipComponent {
	pinCount @0 :DIM;
	pinSpace @1 :DIM;
	pinWidth @2 :DIM;
	padSize  @3 :DIM;
}

struct SMD4Component {
	dim1Body @0: DIM;
	dim1PinEdge @1: DIM;
	dim2Body @2: DIM;
	dim2PinEdge @3: DIM;
	pinContactLength @4: DIM;
	pinContactWidth @5: DIM;
	pinSpacing @6: DIM;

	side1Pins @7: UInt16;
	side2Pins @8: UInt16;
	side3Pins @9: UInt16;
	side4Pins @10: UInt16;
}

# Not just passive components.
#   Tracks any 2-terminal axial, radial, or chip-type component
#

struct Passive2Component {
		enum SymType {
		    res @0;
            cap @1;
            capPol @2;
            ind @ 3;
            diode @4;
        }

		enum BodyType {
		    chip @0;
            thAxial @1;
            thRadial @2;
            thSideCap @3;
            thFlippedCap @4;

		}
        symType @0: SymType;
        bodyType @1: BodyType;

        pinD @2: DIM;
        bodyCornerVec @3: Point2;
        pinCornerVec @4: Point2;

}
	

struct Component {
	common @0 :CmpGeneral;
	union {
		dip @1 :DipComponent;
		smd4 @2 :SMD4Component;
		passive2 @3 :Passive2Component;
	}
}

# Stackup stuff
struct Layer {
	sid @0 :ID;
	name @1 :Text;
	color @2 :Color3f;

	imagelayerSids @3 :List(ID);
}

struct ViaPair {
	sid @0 :ID;

	firstLayerSid @1 :ID;
	secondLayerSid @2 :ID;
}

struct Stackup {
	layers @0 :List(Layer);
	viapairs @1 :List(ViaPair);
}

struct Nets {
	netList @0  :List(Net);
}

struct Project {
	stackup @0 :Stackup;
	imagery @1 :Imagery;
	nets @2 :Nets;
	artwork @3  :Artwork;
}
